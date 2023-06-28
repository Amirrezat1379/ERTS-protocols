#!/usr/bin/env python

"""
taskset.py - parser for task set from JSON file
"""

from task import Task
from taskSetJsonKeys import TaskSetJsonKeys
from printer import printChart

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

    def getTaskSetFeasiblity(self):
        i = 0
        for task in self:
            i += task.getTaskU()
        if i <= 1:
            return True
        return False

    def parseDataToTasks(self, data):
        taskSet = {}

        for taskData in data[TaskSetJsonKeys.KEY_TASKSET]:
            task = Task(taskData)

            if task.id in taskSet:
                print("Error: duplicate task ID: {0}".format(task.id))
                return

            if task.period < 0 and task.relativeDeadline < 0:
                print("Error: aperiodic task must have positive relative deadline")
                return

            taskSet[task.id] = task

        self.tasks = taskSet

    def buildJobReleases(self, data):
        jobs = []

        if TaskSetJsonKeys.KEY_RELEASETIMES in data:  # necessary for sporadic releases
            for jobRelease in data[TaskSetJsonKeys.KEY_RELEASETIMES]:
                releaseTime = float(jobRelease[TaskSetJsonKeys.KEY_RELEASETIMES_JOBRELEASE])
                taskId = int(jobRelease[TaskSetJsonKeys.KEY_RELEASETIMES_TASKID])

                job = self.getTaskById(taskId).spawnJob(releaseTime)
                jobs.append(job)
        else:
            scheduleStartTime = float(data[TaskSetJsonKeys.KEY_SCHEDULE_START])
            scheduleEndTime = float(data[TaskSetJsonKeys.KEY_SCHEDULE_END])
            for task in self:
                t = max(task.offset, scheduleStartTime)
                while t < scheduleEndTime:
                    job = task.spawnJob(t)
                    if job is not None:
                        jobs.append(job)

                    if task.period >= 0:
                        t += task.period  # periodic
                    else:
                        t = scheduleEndTime  # aperiodic

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

class Queue():
    def __init__(self, jobs):
        self.jobs = jobs
        self.locked_semaphore = None
        self.sub_jobs = []

    def setSubJobs(self, tasks):
        i = 0
        j = 0
        for task in tasks:
            i += 1
            for job in task.getJobs():
                for item in job.sections:
                    self.sub_jobs.append([i, int(job.releaseTime), item[0], item[1], job.task.id, j]) #[priority, releaseTime, semaphore, time to use, task id, sub job id]
                    j += 1
    
    def getSubJob(self, time):
        for sub_job in self.sub_jobs:
            if time >= sub_job[1]:
                return sub_job
        
    def addSubJob(self, new_sub_job):
        i = 0
        for sub_job in self.sub_jobs:
            if new_sub_job[0] > sub_job[0]:
                i += 1
                continue
            else:
                self.sub_jobs.insert(i, new_sub_job)
                return
    
    def removeSubJob(self, removing_sub_job):
        i = 0
        for sub_job in self.sub_jobs:
            if sub_job[5] == removing_sub_job[5]:
                del self.sub_jobs[i]
                return
            i += 1

    def getNeedSemaphores(self, finish_time):
        semaphores = {}
        for i in range(finish_time):
            for sub_job in self.sub_jobs:
                if sub_job[1] <= i:
                    if sub_job[2] not in semaphores:
                        if sub_job[4] not in semaphores.values():
                            semaphores[sub_job[2]] = sub_job[4]
        return semaphores
    
    def getSubJobByTaskId(self, id):
        for sub_job in self.sub_jobs:
            if sub_job[4] == id:
                return sub_job


class Scheduler():
    def __init__(self, data):
        self.task_set = TaskSet(data)
        self.queue = Queue(self.task_set.jobs)
        self.end_time = data[TaskSetJsonKeys.KEY_SCHEDULE_END]
        self.current_sub_job = None
        self.executing_task = []
        self.current_semaphore = 0 # Use for NPP protocol
        self.using_semaphore = {} # Use for PIP protocol

    def executeSubJob(self, mode):
        self.current_sub_job[3] -= 1
        if mode == "pip":
            self.using_semaphore[self.current_sub_job[2]] = self.current_sub_job[4]
        else:
            self.current_semaphore = self.current_sub_job[2]
        self.executing_task.append([self.current_sub_job[4], self.current_sub_job[2]])
        if self.current_sub_job[3] == 0:
            self.queue.removeSubJob(self.current_sub_job)
            if mode == "pip":
                self.using_semaphore[self.current_sub_job[2]] = -1
            else:
                self.current_semaphore = 0
            self.current_sub_job = None

    def schedulTasks(self, mode):
        # Sort tasks by their deadline to implement DM scheduling
        sorted_tasks = sorted(self.task_set, key=lambda task: task.deadline)
        # Get sub jobs
        self.queue.setSubJobs(sorted_tasks)
        if mode == "pip":
            for i in range(self.end_time):
                new_sub_job = self.queue.getSubJob(i)
                if self.current_sub_job == None:
                    if new_sub_job == None:
                        # It's flag to know that CPU is idel in that moment
                        self.executing_task.append([-1, -1])
                    else:
                        # Initialize current sub job
                        semaphore = new_sub_job[2]
                        self.current_sub_job = new_sub_job
                        # Check that is semaphore use by task or not
                        if semaphore in self.using_semaphore:
                            if self.using_semaphore[semaphore] != -1:
                                self.current_sub_job = self.queue.getSubJobByTaskId(self.using_semaphore[semaphore])
                        self.queue.removeSubJob(self.current_sub_job)
                        self.executeSubJob(mode)
                else:
                    # We have job in ready queue so we have to check that it can preempt current job or not
                    if new_sub_job:
                        # Same semaphore is in use and there is critical section so we must not change it
                        if new_sub_job[2] in self.using_semaphore and new_sub_job[2] != 0:
                            self.executeSubJob(mode)
                        # New job Needs another semaphore so we have to check their priority
                        else:
                            if new_sub_job[0] < self.current_sub_job[0]:
                                self.queue.addSubJob(self.current_sub_job)
                                self.current_sub_job = new_sub_job
                                self.queue.removeSubJob(new_sub_job)
                            self.executeSubJob(mode)
                    # There is no new job but currently there is job to execute
                    else:
                        self.executeSubJob(mode)
        else:
            for i in range(self.end_time):
                new_sub_job = self.queue.getSubJob(i)
                if self.current_sub_job == None:
                    if new_sub_job == None:
                        # It's flag to know that CPU is idel in that moment
                        self.executing_task.append([-1, -1])
                    else:
                        self.current_sub_job = new_sub_job
                        self.queue.removeSubJob(self.current_sub_job)
                        self.executeSubJob(mode)
                else:
                    # We have job in ready queue so we have to check that it can preempt current job or not
                    if new_sub_job:
                        # Critical section is in use so we must now swap jobs
                        if self.current_semaphore > 0:
                            self.executeSubJob(mode)
                        else:
                            if self.current_sub_job[0] > new_sub_job[0]:
                                self.queue.addSubJob(self.current_sub_job)
                                self.current_sub_job = new_sub_job
                                self.queue.removeSubJob(new_sub_job)
                            self.executeSubJob(mode)
                    else:
                        self.executeSubJob(mode)
        self.task_set.printTasks()
        self.task_set.printJobs()
        if self.task_set.getTaskSetFeasiblity():
            print("Feasible")
        else:
            print("Will miss")
        printChart(self.executing_task)
                    
        # pass
