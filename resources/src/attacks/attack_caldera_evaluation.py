# Copyright 2016, 2017, 2018, 2019, 2020, 2021 Fraunhofer FKIE
#
# This file is part of BREACH.
#
# BREACH is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# BREACH is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with BREACH. If not, see <http://www.gnu.org/licenses/>.

import json
import os
import tempfile

import requests
import time as t
from datetime import datetime, time

from attacks import Attack, AttackInfo, AttackOptions
from attacks.caldera_eval import CALDERAEvaluation as Evaluation

from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search


class CalderaEvaluationAttackOptions(AttackOptions):
    caldera_host = "Host address of the machine CALDERA is running on"
    caldera_port = "Port CALDERA is listening on"
    keep_logs = "Whether or not to delete created log files afterwards"
    log_suffix = "Suffix to be appended to created log files"
    log_dir = "Where to save created log files (full path)"

    def _set_defaults(self):
        self.caldera_host = "http://192.168.56.31"
        self.caldera_port = "8888"
        self.keep_logs = False
        self.log_suffix = "foo"
        self.log_dir = tempfile.gettempdir()


class CalderaEvaluation(Attack):
    info = AttackInfo(
        name="caldera_evaluation",
        description="Runs MITRE's APT29 evaluation on two target clients")
    options_class = CalderaEvaluationAttackOptions

    target1_user = "client1"
    target2_user = "client2"
    target1_ip = "192.168.56.101"
    target2_ip = "192.168.56.102"

    op1_name = "APT29 Day 1.A"
    op2_name = "APT29 Day 1.B"
    op3_name = "APT29 Day 2"
    op1_group = "day_1A"
    op2_group = "day_1B"
    op3_group = "day_2"

    adv1_id = "d6115456-604a-4707-b30e-079dec5aad53"
    adv2_id = "7916aaa3-f05d-453a-b632-f0f73b0865ce"
    adv3_id = "6dc5b558-c7bd-4835-860b-50e003399f8d"

    def run(self):
        self.run_phase_one()
        self.run_phase_two()
        self.run_phase_three()
        self.get_logs()
        self.evaluate_results()

    def run_phase_one(self):
        self.start_agent(self.target1_ip, self.target1_user, self.op1_group)
        self.caldera_start_op(self.op1_name, self.op1_group, self.adv1_id)
        self.wait_for_op(self.op1_name)
        t.sleep(90)  # target1 will reboot after phase one, waiting to ensure new commands can be received

    def run_phase_two(self):
        self.start_agent(self.target1_ip, self.target1_user, self.op2_group)
        self.caldera_start_op(self.op2_name, self.op2_group, self.adv2_id)
        self.wait_for_op(self.op2_name)

    def run_phase_three(self):
        self.start_agent(self.target2_ip, self.target2_user, self.op3_group)
        self.caldera_start_op(self.op3_name, self.op3_group, self.adv3_id)
        self.wait_for_op(self.op3_name)
        t.sleep(180)  # waiting to ensure that all relevant log data has been transmitted to the log server

    def start_agent(self, target_ip, target_user, group_name):
        self.ssh_client.target.hostname = target_ip
        self.ssh_client.target.username = "ssh"
        cmd = (f"schtasks /create /sc once /st 23:59 /tn {group_name} "
               f"/tr \"'C:\\BREACH\\agent_startup.bat' {group_name}\" /ru BREACH\\{target_user} && "
               f"schtasks /run /tn {group_name}")
        self.exec_command_on_target(cmd)
        t.sleep(30)

    def caldera_start_op(self, current_op, current_group, adv_id):
        url = f"{self.options.caldera_host}:{self.options.caldera_port}/api/rest"
        query = {"index": "operations",
                 "name": f"{current_op}",
                 "group": f"{current_group}",
                 "adversary_id": f"{adv_id}",
                 "planner": "atomic",
                 "source": "evals-round-2",
                 "auto_close": "1"}
        headers = {"KEY": "breach"}
        requests.put(url, data=json.dumps(query), headers=headers)

    def wait_for_op(self, op_name):
        print(f"Waiting until operation \"{op_name}\" has finished. May take up to 15 minutes.")
        while self.caldera_get_status(op_name) != "finished":
            t.sleep(10)

    def caldera_get_status(self, current_op):
        url = f"{self.options.caldera_host}:{self.options.caldera_port}/api/rest"
        query = {"index": "operations",
                 "name": f"{current_op}"}
        headers = {"KEY": "breach"}
        status_request = requests.post(url, data=json.dumps(query), headers=headers)
        if "\"state\": \"finished\"," in status_request.text:
            return "finished"
        else:
            return 0

    def get_logs(self):
        elasticsearch_hosts = ['192.168.56.12']
        queries = [{'name': 'syslog', 'search': Search(index='syslog-*')},
                   {'name': 'winlogbeat', 'search': Search(index='winlogbeat-*')}]
        start_time = datetime.combine(datetime.now(), time.min).strftime("%Y-%m-%dT%H:%M:%S")
        end_time = datetime.combine(datetime.now(), time.max).strftime("%Y-%m-%dT%H:%M:%S")
        suffix = self.options.log_suffix

        client = Elasticsearch(elasticsearch_hosts)
        for query in queries:
            filename = query['name'] + '_' + str(suffix) + '.jsonl'
            print('Writing ' + filename + '...')
            with open(os.path.join(self.options.log_dir, filename), 'w') as log_file:
                for hit in query['search'].using(client).filter(
                        'range', **{'@timestamp': {'gte': start_time, 'lt': end_time}}).scan():
                    log_file.write(json.dumps(hit.to_dict(), sort_keys=True) + '\n')

    def evaluate_results(self):
        search_string_dir = os.path.dirname(__file__)
        search_string_dir = search_string_dir + "/caldera_tools/search_strings/"
        log_path = os.path.join(self.options.log_dir, f"winlogbeat_{self.options.log_suffix}.jsonl")
        result = Evaluation().evaluate_logs(log_path, search_string_dir)
        if not self.options.keep_logs:
            self.delete_logs()
        return result

    def delete_logs(self):
        log_dir = self.options.log_dir
        suffix = self.options.log_suffix
        os.remove(os.path.join(log_dir, f"winlogbeat_{suffix}.jsonl"))
        os.remove(os.path.join(log_dir, f"syslog_{suffix}.jsonl"))
