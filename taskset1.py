#!/usr/bin/env python
import matplotlib.pyplot as plt
import json
import sys


class TaskSetJsonKeys(object):
    # Task set
    KEY_TASKSET = "taskset"

    # Task
    KEY_TASK_ID = "taskId"
    KEY_TASK_PERIOD = "period"
    KEY_TASK_WCET = "wcet"
    KEY_TASK_DEADLINE = "deadline"
    KEY_TASK_OFFSET = "offset"
    KEY_TASK_SECTIONS = "sections"

    # Schedule
    KEY_SCHEDULE_START = "startTime"
    KEY_SCHEDULE_END = "endTime"


class TaskSetIterator:
    def __init__(self, taskSet):
        self.taskSet = taskSet
        self.index = 0
        self.keys = iter(taskSet.tasks)

    def __next__(self):
        key = next(self.keys)
        return self.taskSet.tasks[key]


class TaskSet(object):
    def __init__(self, data):
        self.parseDataToTasks(data)
        self.buildJobReleases(data)

    def parseDataToTasks(self, data):
        taskSet = {}

        for taskData in data[TaskSetJsonKeys.KEY_TASKSET]:
            task = Task(taskData)

            if task.id in taskSet:
                print("Error: duplicate task ID: {0}".format(task.id))
                return

            if task.period <= 0 or task.wcet <= 0 or task.relativeDeadline <= 0:
                print("Error: invalid task parameters")
                return

            taskSet[task.id] = task

        self.tasks = taskSet

    def buildJobReleases(self, data):
        jobs = []

        if TaskSetJsonKeys.KEY_SCHEDULE_START in data and TaskSetJsonKeys.KEY_SCHEDULE_END in data:
            scheduleStartTime = float(data[TaskSetJsonKeys.KEY_SCHEDULE_START])
            scheduleEndTime = float(data[TaskSetJsonKeys.KEY_SCHEDULE_END])

            for task in self:
                t = max(task.offset, scheduleStartTime)
                while t < scheduleEndTime:
                    job = task.spawnJob(t)
                    jobs.append(job)
                    t += task.period

        self.jobs = jobs

    def __contains__(self, elt):
        return elt in self.tasks

    def __iter__(self):
        return TaskSetIterator(self)

    def __len__(self):
        return len(self.tasks)

    def getTaskById(self, taskId):
        return self.tasks[taskId]

    def printTasks(self):
        print("\nTask Set:")
        for task in self:
            print(task)

    def printJobs(self):
        print("\nJobs:")
        for task in self:
            for job in task.getJobs():
                print(job)


class Scheduler:
    def __init__(self, task_set):
        self.task_set = task_set

    def schedule_jobs(self):
        # Sort tasks based on their periods (DM algorithm)
        sorted_tasks = sorted(self.task_set, key=lambda task: task.period)

        # Initialize resource locks
        resource_locks = {}

        for task in sorted_tasks:
            # Check resource access for each section
            for section in task.sections:
                resource_id = section[0]
                duration = section[1]

                # Check if the resource is locked by other tasks
                if resource_id in resource_locks:
                    locked_task = resource_locks[resource_id]

                    # If the locked task has a higher priority, skip the section
                    if locked_task.priority > task.priority:
                        continue

                    # If the locked task has a lower priority, preempt it
                    self.preempt_task(locked_task)

                # Lock the resource for the current task
                resource_locks[resource_id] = task

                # Execute the section for the specified duration
                self.execute_section(task, section)

                # Release the resource lock
                del resource_locks[resource_id]

    def preempt_task(self, task):
        # Preempt the currently executing task
        print(f"Preempting task {task.task_id}")

    def execute_section(self, task, section):
        # Execute the section for the specified duration
        resource_id = section[0]
        duration = section[1]
        print(f"Executing section for task {task.id}: Resource ID={resource_id}, Duration={duration}")


class Queue:
    def __init__(self, scheduler):
        self.jobs = []
        self.scheduler = scheduler

    def add_job(self, job):
        self.jobs.append(job)

    def run(self):
        while self.jobs:
            job = self.scheduler.schedule(self.jobs)
            if job:
                job.execute()
                if job.is_completed():
                    self.jobs.remove(job)


class Task(object):
    def __init__(self, taskDict):
        self.id = int(taskDict[TaskSetJsonKeys.KEY_TASK_ID])
        self.period = float(taskDict[TaskSetJsonKeys.KEY_TASK_PERIOD])
        self.wcet = float(taskDict[TaskSetJsonKeys.KEY_TASK_WCET])
        self.relativeDeadline = float(
            taskDict.get(TaskSetJsonKeys.KEY_TASK_DEADLINE, taskDict[TaskSetJsonKeys.KEY_TASK_PERIOD]))
        self.offset = float(taskDict.get(TaskSetJsonKeys.KEY_TASK_OFFSET, 0.0))
        self.sections = taskDict[TaskSetJsonKeys.KEY_TASK_SECTIONS]

        self.lastJobId = 0
        self.lastReleasedTime = 0.0

        self.jobs = []

    def getAllResources(self):
        resources = set()
        for section in self.sections:
            resource_id = section[0]
            resources.add(resource_id)
        return resources

    def spawnJob(self, releaseTime):
        if self.lastReleasedTime > 0 and releaseTime < self.lastReleasedTime:
            print("INVALID: release time of job is not monotonic")
            return None

        if self.lastReleasedTime > 0 and releaseTime < self.lastReleasedTime + self.period:
            print("INVALID: release times are not separated by period")
            return None

        self.lastJobId += 1
        self.lastReleasedTime = releaseTime

        job = Job(self, self.lastJobId, releaseTime)

        self.jobs.append(job)
        return job

    def getJobs(self):
        return self.jobs

    def getJobById(self, jobId):
        if jobId > self.lastJobId:
            return None

        job = self.jobs[jobId - 1]
        if job.id == jobId:
            return job

        for job in self.jobs:
            if job.id == jobId:
                return job

        return None

    def getUtilization(self):
        total_execution_time = sum(section[1] for section in self.sections)
        return total_execution_time / self.period

    def __str__(self):
        return "task {0}: (Φ,T,C,D,∆) = ({1}, {2}, {3}, {4}, {5})".format(
            self.id, self.offset, self.period, self.wcet, self.relativeDeadline, self.sections)


class Job(object):
    def __init__(self, task, jobId, releaseTime):
        self.task = task
        self.id = jobId
        self.releaseTime = releaseTime
        self.deadline = releaseTime + task.relativeDeadline
        self.sections = task.sections[:]
        self.currentSection = None
        self.remainingSectionTime = 0

    def getResourceHeld(self):
        if self.currentSection is not None:
            return self.currentSection[0]
        return None

    def getRecourseWaiting(self):
        if self.currentSection is None and len(self.sections) > 0:
            return self.sections[0][0]
        return None

    def getRemainingSectionTime(self):
        return self.remainingSectionTime

    def execute(self):
        if self.currentSection is None:
            self.currentSection = self.sections.pop(0)
            self.remainingSectionTime = self.currentSection[1]
            print(
                f"Job {self.id}: Started execution of section for Resource {self.currentSection[0]} (Duration: {self.currentSection[1]})")
        else:
            self.remainingSectionTime -= 1
            if self.remainingSectionTime <= 0:
                self.currentSection = None
                print(f"Job {self.id}: Completed execution of section")

    def is_completed(self):
        return len(self.sections) == 0

    def __str__(self):
        return "job {0} of task {1}: release time {2}, deadline {3}".format(
            self.id, self.task.id, self.releaseTime, self.deadline)


def loadTaskSetFromJsonFile(filename):
    try:
        with open(filename) as file:
            data = json.load(file)
            taskSet = TaskSet(data)
            return taskSet
    except IOError:
        print("Error: Failed to open or read the JSON file")
        sys.exit(1)
    except json.JSONDecodeError:
        print("Error: Invalid JSON file")
        sys.exit(1)

def plot_scheduled_tasks(task_set):
    fig, ax = plt.subplots()
    for task in task_set:
        for job in task.getJobs():
            for section in job.sections:
                section_start = section[0]
                section_duration = section[1]
                ax.broken_barh([(job.releaseTime + section_start, section_duration)], (task.id-0.4, 0.8), facecolors='C'+str(section_start))
    ax.set_ylim(0, len(task_set))
    ax.set_xlim(0, max(job.deadline for task in task_set for job in task.getJobs()))
    ax.set_xlabel('Time')
    ax.set_ylabel('Task ID')
    ax.set_title('Scheduled Tasks')
    plt.yticks(range(1, len(task_set)+1), [f"Task {task.id}" for task in task_set])
    plt.show()

def main():
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        print("Usage: python scheduler.py <json_file>")
        sys.exit(1)

    with open(file_path) as json_data:
        data = json.load(json_data)

    # Create TaskSet object
    task_set = TaskSet(data)

    # Create Scheduler object
    scheduler = Scheduler(task_set)

    # Schedule jobs
    scheduler.schedule_jobs()

    # Plot scheduled tasks
    plot_scheduled_tasks(task_set)

if __name__ == "__main__":
    main()
