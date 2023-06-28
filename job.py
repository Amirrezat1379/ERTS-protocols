class Job(object):
    def __init__(self, task, jobId, releaseTime):
        # @TODO
        self.task = task
        self.id = jobId
        self.releaseTime = releaseTime
        self.deadline = task.offset + task.relativeDeadline
        self.sections = task.sections[:]
        self.currentSection = None
        self.remainingSections = self.getNumberOfSections()

    def getNumberOfSections(self):
        sections = []
        for item in self.sections:
            if item[0] in sections:
                continue
            else:
                sections.append(item[0])
        return len(sections)

    def getResourceHeld(self):
        '''the resources that it's currently holding'''
        return self.sections[self.currentSection][0]

    # def getRecourseWaiting(self):
    #     '''a resource that is being waited on, but not currently executing'''
    #     @TODO
        
    def getRemainingSectionTime(self):
        return self.sections[self.currentSection][1]

    def execute(self, time):
        self.task.wcet -= 1
        self.sections[self.currentSection][1] -= 1
        if self.sections[self.currentSection][1] == 0:
            self.currentSection += 1
        
    # def executeToCompletion(self):
    #     @TODO

    def isCompleted(self):
        if self.task.wcet == 0:
            return True
        return False

    def __str__(self):
        return "[{0}:{1}] released at {2} -> deadline at {3}".format(self.task.id, self.id, self.releaseTime,
                                                                     self.deadline)