#!/usr/bin/python3

# run "python3 caldera_eval_standalone.py -h" for help

import argparse
import re
import subprocess
import sys

from dateutil.parser import *

parser = argparse.ArgumentParser(description="This script evaluates the success of "
                                             "CALDERA during a SOCBED simulation.")
parser.add_argument("jsonl_log_file", metavar="jsonl_log_file", type=str,
                    help=".jsonl file generated by a SOCBED simulation")
parser.add_argument("search_strings_dir", metavar="search_strings_dir", type=str,
                    help="path to directory containing the layer1/layer2 strings for each ability")
parser.add_argument("-v", "--verbose", action="store_true",
                    help="increase output verbosity")
parser.add_argument("-t", "--times", action="store_true",
                    help="show individual runtime of each ability")
args = parser.parse_args()

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

day1a_counter = []
day1b_counter = []
day2_counter = []

individual_timestamps_per_ability = [[], [], []]
total_runtime_per_ability = [[], []]

ability_failures = []
sync_failures = []
max_timestamp = ""

# formatting shortcuts
green = "\033[92m"
red = "\033[91m"
bold = "\033[1m"
uline = "\033[4m"
end = "\033[0m"


def calculate_op_duration(target):
    start_end_abilities = [["day1.A_1.A", "day1.A_10.A.2"],
                           ["day1.B_9.B.1", "day1.B_9.C"],
                           ["day2_0.0", "day2_20.B"]]
    op_start_timestamp = op_end_timestamp = None
    for (ability, timestamp) in zip(individual_timestamps_per_ability[0],
                                    individual_timestamps_per_ability[1]):
        if ability == start_end_abilities[target][0]:
            op_start_timestamp = timestamp
        elif ability == start_end_abilities[target][1]:
            op_end_timestamp = timestamp

    if op_start_timestamp and op_end_timestamp:
        return op_end_timestamp - op_start_timestamp
    return f"{red}ERROR! Ability {start_end_abilities[target][0]} or " \
           f"{start_end_abilities[target][1]} failed, can't calculate duration{end}"


def output_summary():
    print(f"{bold}{uline}SUMMARY:{end}")
    print(f"Day 1.A:	{day1a_counter.count('success')}/{len(day1a_abilities)} abilities successful, "
          f"{day1a_counter.count('skipped')} skipped, "
          f"{day1a_counter.count('failure')} failed. [Duration: {calculate_op_duration(0)}]")
    print(f"Day 1.B:	 {day1b_counter.count('success')}/ {len(day1b_abilities)} abilities successful, "
          f"{day1b_counter.count('skipped')} skipped, "
          f"{day1b_counter.count('failure')} failed. [Duration: {calculate_op_duration(1)}]")
    print(f"Day 2  :	{day2_counter.count('success')}/{len(day2_abilities)} abilities successful, "
          f"{day2_counter.count('skipped')} skipped, "
          f"{day2_counter.count('failure')} failed. [Duration: {calculate_op_duration(2)}]\n")

    if ability_failures or sync_failures:
        if sync_failures:
            print(f"{red}Abilities did not execute in the correct order!\n"
                  f"TIMESTAMP_ERROR in {sync_failures}{end}\n")
        if ability_failures:
            print(f"{red}Ability not included in exceptions failed!\n"
                  f"ABILITY_ERROR in {ability_failures}{end}\n")
        return 1
    return 0


def output_ability_runtimes():
    print(f"{bold}{uline}INDIVIDUAL ABILITY RUNTIMES:{end}")
    print("Note that only successfully executed abilities are shown here.")
    row_format = '{:<16}' * len(total_runtime_per_ability)
    for entry in zip(*total_runtime_per_ability):
        print("_" * 25)
        print(row_format.format(*entry))
    print("_" * 25 + "\n")


def check_for_sync_failure(current_timestamp, current_ability):
    global max_timestamp
    if max_timestamp > current_timestamp:
        sync_failures.append(current_ability)
    else:
        max_timestamp = current_timestamp


def check_for_exception(current_ability):
    if current_ability not in exceptions:
        ability_failures.append(current_ability)


def calculate_ability_duration(current_ability, start_timestamp, end_timestamp):
    start_timestamp = parse(start_timestamp)
    end_timestamp = parse(end_timestamp)
    ability_duration = end_timestamp - start_timestamp

    total_runtime_per_ability[0].append(current_ability)
    total_runtime_per_ability[1].append(str(ability_duration)[2:-3])

    individual_timestamps_per_ability[0].append(current_ability)
    individual_timestamps_per_ability[1].append(start_timestamp)
    individual_timestamps_per_ability[2].append(end_timestamp)


def get_latest_timestamp(grep_output, current_ability):
    target_timestamp = "0"
    for line in grep_output.splitlines():
        timestamp_search = re.search("@timestamp\": \"(.+?)\",", line)
        current_timestamp = timestamp_search.group(1)
        if current_timestamp > target_timestamp:
            target_timestamp = current_timestamp

    check_for_sync_failure(target_timestamp, current_ability)
    return target_timestamp


def get_earliest_timestamp(grep_output, current_ability):
    target_timestamp = "9999"
    for line in grep_output.splitlines():
        timestamp_search = re.search("@timestamp\": \"(.+?)\",", line)
        current_timestamp = timestamp_search.group(1)
        if current_timestamp < target_timestamp:
            target_timestamp = current_timestamp

    check_for_sync_failure(target_timestamp, current_ability)
    return target_timestamp


def check_if_successful(current_ability, log_file, search_strings_dir, current_counter):
    search_command = f"grep -F -f {search_strings_dir}{current_ability}_layer2.txt {log_file}"
    search_process = subprocess.Popen(search_command, shell=True,
                                      universal_newlines=True, stdout=subprocess.PIPE)
    grep_output = search_process.communicate()[0]
    if grep_output:
        timestamp = get_latest_timestamp(grep_output, current_ability)
        print(f"{green}Ability executed successfully!{end}    [Timestamp is {timestamp}]\n")
        current_counter.append("success")
        return timestamp
    else:
        print(f"{red}Ability failed!{end}\n")
        current_counter.append("failure")
        check_for_exception(current_ability)
        return None


def check_if_executed(current_ability, log_file, search_strings_dir, current_counter):
    search_command = f"grep -F -f {search_strings_dir}{current_ability}_layer1.txt {log_file}"
    search_process = subprocess.Popen(search_command, shell=True,
                                      universal_newlines=True, stdout=subprocess.PIPE)
    grep_output = search_process.communicate()[0]
    if grep_output:
        timestamp = get_earliest_timestamp(grep_output, current_ability)
        print(f"{green}Ability has been triggered.{end}       [Timestamp is {timestamp}]")
        return timestamp
    else:
        print(f"{red}Ability has not been triggered!{end}\n")
        current_counter.append("skipped")
        check_for_exception(current_ability)
        return None


def check_operation(operation_abilities, current_counter, log_file, search_strings_dir):
    for ability in operation_abilities:
        print(f"{bold}{uline}Ability {ability}:{end}")
        start_timestamp = check_if_executed(ability, log_file, search_strings_dir, current_counter)
        if start_timestamp:
            end_timestamp = check_if_successful(ability, log_file, search_strings_dir, current_counter)
            if end_timestamp:
                calculate_ability_duration(ability, start_timestamp, end_timestamp)


check_operation(day1a_abilities, day1a_counter, args.jsonl_log_file, args.search_strings_dir)
check_operation(day1b_abilities, day1b_counter, args.jsonl_log_file, args.search_strings_dir)
check_operation(day2_abilities, day2_counter, args.jsonl_log_file, args.search_strings_dir)
output_ability_runtimes()
sys.exit(output_summary())
