#!/usr/bin/python3

import re
import subprocess
from dateutil.parser import parse


class CALDERAEvaluation:
    day1a_abilities = ["day1.A_1.A", "day1.A_1.B", "day1.A_2.A", "day1.A_2.B.1", "day1.A_3.A", "day1.A_3.B.1",
                       "day1.A_3.B.2", "day1.A_4.A", "day1.A_4.B.1", "day1.A_4.B.2", "day1.A_4.C", "day1.A_5.A",
                       "day1.A_5.B", "day1.A_6.A", "day1.A_6.B.1", "day1.A_7.A.0", "day1.A_7.A.1", "day1.A_7.A.2",
                       "day1.A_7.A.3", "day1.A_7.B", "day1.A_8.A.1", "day1.A_8.A.2", "day1.A_8.B", "day1.A_10.B",
                       "day1.A_10.A.3", "day1.A_10.A.2"]
    day1b_abilities = ["day1.B_9.B.1", "day1.B_9.B.8", "day1.B_9.C"]
    day2_abilities = ["day2_0.0",
                      "day2_11.A", "day2_12.A", "day2_12.B", "day2_12.C", "day2_13.A", "day2_13.B", "day2_13.C",
                      "day2_13.D", "day2_14.A", "day2_14.C", "day2_14.B", "day2_15.A", "day2_16.A", "day2_16.B",
                      "day2_16.C.D", "day2_17.A", "day2_17.B.C", "day2_18.A", "day2_19.A", "day2_20.A.1", "day2_20.B"
                      ]

    exceptions = ["day1.A_1.B", "day1.A_7.A.2", "day1.A_8.B", "day1.A_10.A.3", "day2_15.A", "day2_16.C.D", "day2_18.A",
                  "day2_20.A.1"
                  ]

    # Abilities that are currently allowed/expected to be skipped or fail:
    #    1.B: gets skipped if powershell environment is present, which seems to be always the case
    #  7.A.2: requires non-empty clipboard, which won't happen during automated tests -> fails
    #    8.B: skipped due to partial failure of 8.A.2 (caused by connection problems within the domain)
    # 10.A.3: is supposed to clean up artifacts from previous abilities, but for some reason these don't exist -> fails
    #   15.A: checks if a certain WMI-class ("__Filter") is present and fails if that's the case
    # 16.C.D: fails due to connection problems within the domain
    #   18.A: skipped due to one-drive not being configured within SOCBED
    # 20.A.1: skipped because 16.C.D failed (consequential failure)

    day1a_counter = []
    day1b_counter = []
    day2_counter = []

    individual_timestamps_per_ability = [[], [], []]
    total_runtime_per_ability = [[], []]

    ability_failures = []
    sync_failures = []
    global_max_timestamp = ""

    log_file = ""
    search_strings_directory = ""

    # formatting shortcuts
    green = "\033[92m"
    red = "\033[91m"
    bold = "\033[1m"
    uline = "\033[4m"
    end = "\033[0m"

    def evaluate_logs(self, jsonl_log_file, search_strings_dir):
        self.log_file = jsonl_log_file
        self.search_strings_directory = search_strings_dir

        self.check_operation(self.day1a_abilities, self.day1a_counter)
        self.check_operation(self.day1b_abilities, self.day1b_counter)
        self.check_operation(self.day2_abilities, self.day2_counter)
        self.output_ability_runtimes()
        return self.output_summary()

    def check_operation(self, operation_abilities, current_counter):
        for ability in operation_abilities:
            print(f"{self.bold}{self.uline}Ability {ability}:{self.end}")
            start_timestamp = self.check_if_executed(ability, current_counter)
            if start_timestamp:
                end_timestamp = self.check_if_successful(ability, current_counter)
                if end_timestamp:
                    self.calculate_ability_duration(ability, start_timestamp, end_timestamp)

    def check_if_executed(self, current_ability, current_counter):
        search_command = f"grep -F -f {self.search_strings_directory}{current_ability}_layer1.txt {self.log_file}"
        search_process = subprocess.Popen(search_command, shell=True,
                                          universal_newlines=True, stdout=subprocess.PIPE)
        grep_output = search_process.communicate()[0]
        if grep_output:
            timestamp = self.get_earliest_timestamp(grep_output, current_ability)
            print(f"{self.green}Ability has been triggered.{self.end}       [Timestamp is {timestamp}]")
            return timestamp
        else:
            print(f"{self.red}Ability has not been triggered!{self.end}\n")
            current_counter.append("skipped")
            self.check_for_exception(current_ability)
            return None

    def check_if_successful(self, current_ability, current_counter):
        search_command = f"grep -F -f {self.search_strings_directory}{current_ability}_layer2.txt {self.log_file}"
        search_process = subprocess.Popen(search_command, shell=True,
                                          universal_newlines=True, stdout=subprocess.PIPE)
        grep_output = search_process.communicate()[0]
        if grep_output:
            timestamp = self.get_latest_timestamp(grep_output, current_ability)
            print(f"{self.green}Ability executed successfully!{self.end}    [Timestamp is {timestamp}]\n")
            current_counter.append("success")
            return timestamp
        else:
            print(f"{self.red}Ability failed!{self.end}\n")
            current_counter.append("failure")
            self.check_for_exception(current_ability)
            return None

    def get_earliest_timestamp(self, grep_output, current_ability):
        target_timestamp = "9999"
        for line in grep_output.splitlines():
            timestamp_search = re.search("@timestamp\": \"(.+?)\",", line)
            current_timestamp = timestamp_search.group(1)
            if current_timestamp < target_timestamp:
                target_timestamp = current_timestamp

        self.check_for_sync_failure(target_timestamp, current_ability)
        return target_timestamp

    def get_latest_timestamp(self, grep_output, current_ability):
        target_timestamp = "0"
        for line in grep_output.splitlines():
            timestamp_search = re.search("@timestamp\": \"(.+?)\",", line)
            current_timestamp = timestamp_search.group(1)
            if current_timestamp > target_timestamp:
                target_timestamp = current_timestamp

        self.check_for_sync_failure(target_timestamp, current_ability)
        return target_timestamp

    def calculate_ability_duration(self, current_ability, start_timestamp, end_timestamp):
        start_timestamp = parse(start_timestamp)
        end_timestamp = parse(end_timestamp)
        ability_duration = end_timestamp - start_timestamp

        self.total_runtime_per_ability[0].append(current_ability)
        self.total_runtime_per_ability[1].append(str(ability_duration)[2:-3])

        self.individual_timestamps_per_ability[0].append(current_ability)
        self.individual_timestamps_per_ability[1].append(start_timestamp)
        self.individual_timestamps_per_ability[2].append(end_timestamp)

    def check_for_exception(self, current_ability):
        if current_ability not in self.exceptions:
            self.ability_failures.append(current_ability)

    def check_for_sync_failure(self, current_timestamp, current_ability):
        if self.global_max_timestamp > current_timestamp:
            self.sync_failures.append(current_ability)
        else:
            self.global_max_timestamp = current_timestamp

    def output_ability_runtimes(self):
        print(f"{self.bold}{self.uline}INDIVIDUAL ABILITY RUNTIMES:{self.end}")
        print("Note that only successfully executed abilities are shown here.")
        row_format = '{:<16}' * len(self.total_runtime_per_ability)
        for entry in zip(*self.total_runtime_per_ability):
            print("_" * 25)
            print(row_format.format(*entry))
        print("_" * 25 + "\n")

    def output_summary(self):
        print(f"{self.bold}{self.uline}SUMMARY:{self.end}")
        print(f"Day 1.A:	{self.day1a_counter.count('success')}/{len(self.day1a_abilities)} abilities successful, "
              f"{self.day1a_counter.count('skipped')} skipped, "
              f"{self.day1a_counter.count('failure')} failed. [Duration: {self.calculate_op_duration(0)}]")
        print(f"Day 1.B:	 {self.day1b_counter.count('success')}/ {len(self.day1b_abilities)} abilities successful, "
              f"{self.day1b_counter.count('skipped')} skipped, "
              f"{self.day1b_counter.count('failure')} failed. [Duration: {self.calculate_op_duration(1)}]")
        print(f"Day 2  :	{self.day2_counter.count('success')}/{len(self.day2_abilities)} abilities successful, "
              f"{self.day2_counter.count('skipped')} skipped, "
              f"{self.day2_counter.count('failure')} failed. [Duration: {self.calculate_op_duration(2)}]\n")

        if self.ability_failures or self.sync_failures:
            if self.sync_failures:
                print(f"{self.red}Abilities did not execute in the correct order!\n"
                      f"TIMESTAMP_ERROR in {self.sync_failures}{self.end}\n")
            if self.ability_failures:
                print(f"{self.red}Ability not included in exceptions failed!\n"
                      f"ABILITY_ERROR in {self.ability_failures}{self.end}\n")
            return 1
        return 0

    def calculate_op_duration(self, target):
        start_end_abilities = [["day1.A_1.A", "day1.A_10.A.2"],
                               ["day1.B_9.B.1", "day1.B_9.C"],
                               ["day2_0.0", "day2_20.B"]]
        op_start_timestamp = op_end_timestamp = None
        for (ability, timestamp) in zip(self.individual_timestamps_per_ability[0],
                                        self.individual_timestamps_per_ability[1]):
            if ability == start_end_abilities[target][0]:
                op_start_timestamp = timestamp
            elif ability == start_end_abilities[target][1]:
                op_end_timestamp = timestamp

        if op_start_timestamp and op_end_timestamp:
            return op_end_timestamp - op_start_timestamp
        return f"{self.red}ERROR! Ability {start_end_abilities[target][0]} or " \
               f"{start_end_abilities[target][1]} failed, can't calculate duration{self.end}"
