import json
import sys
from taskset import Scheduler

if __name__ == "__main__":
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = "taskset.json"

    with open(file_path) as json_data:
        data = json.load(json_data)

    taskSet = Scheduler(data)
    mode = input("Which of the resource access protocols do you want?! pip or npp?! ")
    mode = mode.lower()
    taskSet.schedulTasks(mode)
    # taskSet.printTasks()
    # taskSet.printJobs()