#!/usr/bin/python3
#from calendar import c
import sys
import os
import copy
import argparse
import statistics
import glob
import subprocess
import re
import time

from string import digits

class LogLine:
	remove_digits = str.maketrans('', '', digits)
	def __init__(self):
		self.lineNum = 0
		self.timeStamp = 0
		self.delta = 0
		self.deltaDiff = 0
		self.text = "none"
		self.textKey = "none"

	def parse(self, index, line, priorTimeStamp):
		_line = line.strip()
		words = _line.split("]", 1)
		timeString = words[0].strip(" [")
		self.lineNum = index
		self.timeStamp = float(timeString)
		self.delta = self.timeStamp - priorTimeStamp
		self.text = words[1][:150]
		self.textKey = self.text.translate(self.remove_digits)
		priorTimeStamp = self.timeStamp
		return self

	def getTextKey(self):
		textKey = self.textKey
		return textKey

	def print(self):
		print("I, {:5d}, T, {:8.4f}, D, {: .4f}, DD, ({: .4f}) {}".format(self.lineNum, self.timeStamp, self.delta, self.deltaDiff, self.text))

	def toString(self):
		return "I, {:5d}, T, {:8.4f}, D, {: .4f}, DD, ({: .4f}) {}".format(self.lineNum, self.timeStamp, self.delta, self.deltaDiff, self.text)

def sortByDelta(item):
	return item.delta

def sortByTimeStamp(item):
	return item.timeStamp

class LogLineListStats:
	def __init__(self):
		self.numItems = 0
		self.firstTimeStamp = 0
		self.lastTimeStamp = 0
		self.deltaSum = 0
		self.deltaDiffSum = 0
		self.status = "unknown"
		self.name = "unknown"

	def print(self):
		print("Name {:25} NumItems {:4d} FirstTimeStamp {:.3f}, lastTimeStamp {:.3f}, deltaTime {:.3f} deltaSum {:.3f}, deltaDiffSum {:.3f} Status {}".format(self.name, self.numItems, self.firstTimeStamp, self.lastTimeStamp, (self.lastTimeStamp - self.firstTimeStamp), self.deltaSum, self.deltaDiffSum, self.status))

	def add(self, _other):
		if (_other.firstTimeStamp< self.firstTimeStamp):
				self.firstTimeStamp = _other.firstTimeStamp

		if (_other.lastTimeStamp > self.lastTimeStamp):
			self.lastTimeStamp = _other.lastTimeStamp
		self.deltaSum += _other.deltaSum


# ------------------------------------------------------

class LogLineList:

	def __init__(self, _name= ""):
		self.list = []
		self.name = _name

	def clear(self):
		self.list.clear()

	def append(self, item):
		self.list.append(item)

	def print(self, numItems=None):
		printLineNum = 0
		timeStart = 0
		sumDelta = 0
		sumDeltaDiff = 0
		print("List: {}", self.name)
		for item in self.list:
			if (timeStart==0):
				timeStart = item.timeStamp
			timeOffset = item.timeStamp - timeStart
			sumDelta += item.delta
			sumDeltaDiff += item.deltaDiff
			printLineNum += 1
			printLine = "{:4d} {:.4f} {: .4f} ({: .4f}) | {} ".format(printLineNum, timeOffset, sumDelta, sumDeltaDiff, item.toString())
			print(printLine)
			if (numItems!=None):
				numItems -= 1
				if (numItems<=0):
					break

	def find(self, word):
		itemList = []
		for item in self.list:
			if item.text.find(word) != -1:
				itemList.append(item)
		return itemList
	def findFirst(self, word):
		itemList = self.find(word)
		if (itemList!=None):
			if (len(itemList)>0):
				return itemList[0]
		return None

	def findTextKey(self, textKey):
		itemList = []
		for item in self.list:
			if item.getTextKey()==textKey:
				itemList.append(item)
		if (len(itemList)==0):
			return None
		return itemList[0]

	def findItem(self, item):
		textKey = item.getTextKey()
		return self.findTextKey(textKey)

	def findExactItem(self, item):
		text = item.text
		return self.find(text)

	def filter(self, startKeyWord, endKeyWord, delta=0):
		resultsList = LogLineList()
		startTime = self.findFirst(startKeyWord).timeStamp
		endTime = self.findFirst(endKeyWord).timeStamp
		for item in self.list:
			if ((item.timeStamp >= startTime) and (item.timeStamp<=endTime)):
				if (item.timeStamp == startTime):
					item.delta = 0
				if ((item.delta > delta) or ((item.timeStamp == startTime))):
					resultsList.append(item)
		resultsList.name = self.name
		return resultsList


	def findCommon(self, otherList):
		commonList = LogLineList()
		commonList.name = self.name + "_common"
		notCommonList = LogLineList()
		notCommonList.name = self.name + "_notCommon"
		numFoundItems = 0
		numNotFoundItems = 0
		for item in self.list:
			dm1 = otherList.findExactItem(item)
			_item = copy.deepcopy(item)
			if dm1!=None:
				commonList.append(_item)
				numFoundItems += 1
			else:
				notCommonList.append(_item)
				numNotFoundItems += 1
		print("FindCommon {} {} {} {}".format(len(self.list), len(otherList.list), numFoundItems, numNotFoundItems  ))
		return commonList, notCommonList

	def difference(self, otherList):
		diffList = LogLineList()
		diffList.name = otherList.name + "Diff"
		for item in self.list:
			thisItem = copy.deepcopy(item)
			otherItem = otherList.findItem(item)
			if (item.text.find("EXT4-fs (sda11): recovery complete")!=-1):
				print("here")
			if otherItem==None:
				print("LogLineList::difference() !Error, other does not have {}".format(item.text))
			else:
				thisItem.deltaDiff = otherItem.delta - item.delta

			diffList.append(thisItem)
		return diffList

	def analyze(self, checkPeriod = True, includeFirst = True):
		numItems = 0
		firstTimeStamp = 0
		firstDelta = 0
		lastTimeStamp = 0
		deltaSum = 0
		deltaDiffSum = 0
		for item in self.list:
			numItems += 1
			deltaSum += item.delta
			deltaDiffSum += item.deltaDiff
			if firstTimeStamp==0:
				firstTimeStamp = item.timeStamp
				firstDelta = item.delta
				deltaSum = 0
				deltaDiffSum = 0
			if (item.timeStamp<firstTimeStamp):
				firstTimeStamp = item.timeStamp
				firstDelta = item.delta

			if (item.timeStamp > lastTimeStamp):
				lastTimeStamp = item.timeStamp
		timePeriod = lastTimeStamp - firstTimeStamp
		status = "pass"
		if (checkPeriod):
			diff = timePeriod - deltaSum
			if (abs(diff)>0.0001):
				print("LogLineList::Analyze() {} ERROR! TimePeriod:{}, CumulativeDelta: {} ".format(self.name, timePeriod, deltaSum))
				status = "ERROR"
		logLineListStats = LogLineListStats()
		logLineListStats.numItems = numItems
		logLineListStats.firstTimeStamp = firstTimeStamp
		logLineListStats.lastTimeStamp = lastTimeStamp
		logLineListStats.deltaSum = deltaSum
		logLineListStats.deltaDiffSum = deltaDiffSum
		logLineListStats.status = status
		logLineListStats.name = self.name
		return logLineListStats

	def addList(self, otherList):
		self.list.extend(otherList.list)
		self.list = sorted(self.list, key=sortByTimeStamp)


class LogFile:
	priorTimeStamp = 0.0
	def __init__(self, _fileName = ""):
		self.logLineList = LogLineList()
		if (_fileName!=""):
			self.load(_fileName)

	def loadLines(self, lines):
		logLineList = LogLineList()
		for index, line in enumerate(lines):
			logLine = LogLine().parse(index, line, self.priorTimeStamp)
			self.priorTimeStamp = logLine.timeStamp
			logLineList.append(logLine)
		return logLineList

	def load(self, _fileName):
		self.name = _fileName
		try:
			file = open(_fileName, 'r')
			lines = file.readlines()
			self.logLineList = self.loadLines(lines)
			file.close()
		except:
			print("Error, file '{}' does not exist".format(self.name))

	def print(self, numItems=None):
		self.logLineList.print(numItems)

# -----------------------------------------------------

class MetricSet:
	def __init__(self, _names):
		self.columnNames = _names
		self.rowColArray = []
		self.rowSum = []
		self.rowMax = []
		self.rowMin = []
		self.rowStd = []
		self.rowMedian = []
		for col in self.columnNames:
			self.rowSum.append(0)
			self.rowMax.append(0)
			self.rowMin.append(sys.maxsize)
			self.rowStd.append(0)
			self.rowMedian.append(0)

	def appendSet(self, values):
		self.rowColArray.append(values)

	def print(self):
		print("{}".format("  Line#"), end='')
		for words in self.columnNames:
			print(", '{}'".format(words), end='')
		print("")

		for row, values in enumerate(self.rowColArray):
			print("{:6d}".format(row), end='')
			for col, value in enumerate(values):
				print(", {:.3f}".format(value), end='')
			print("")

		print("{}".format("   MAX"), end='')
		for value in self.rowMax:
			print(", {:.3f}".format(value), end='')
		print("")


		print("{}".format("   AVE"), end='')
		for value in self.rowSum:
			print(", {:.3f}".format(value), end='')
		print("")

		print("{}".format("   MIN"), end='')
		for value in self.rowMin:
			print(", {:2.3f}".format(value), end='')
		print("")

		print("{}".format("   STD"), end='')
		for value in self.rowStd:
			print(", {:2.3f}".format(value), end='')
		print("")

		print("{}".format("MEDIAN"), end='')
		for value in self.rowMedian:
			print(", {:2.3f}".format(value), end='')
		print("")

	def analyze(self):
		stdCols = []
		numCols = len(self.columnNames)
		numRows = len(self.rowColArray)
		for col in range(numCols):
			stdCols.append([])

		# compute sum
		for row, values in enumerate(self.rowColArray):
			for col, value in enumerate(values):
				self.rowSum[col] += value
				if value > self.rowMax[col]:
					self.rowMax[col] = value
				if value < self.rowMin[col]:
					self.rowMin[col] = value

		# compute std
		for col in range(numCols):
			for row in range(numRows):
				try:
					val = self.rowColArray[row][col]
					stdCols[col].append(val)
				except IndexError:
					i = 3
		for col, colList in enumerate(stdCols):
			stdValue = 0
			if (len(colList)>0):
				stdValue = statistics.pstdev(colList)
				stdMedian = statistics.median(colList)
			self.rowStd[col] = stdValue
			self.rowMedian[col] = stdMedian

		#compute average
		for col, value in enumerate(self.rowSum):
			if numRows > 0:
				self.rowSum[col] = self.rowSum[col] / numRows
			else:
				self.rowSum[col] = 0

class AnalyzeFile:
	initFirstTime = 0
	initSecondTime = 0

	def __init__(self, _fileName, _keyWords = ["init first", "init second", "boot_completed"]):
		self.fileName = _fileName
		self.logFile = LogFile(_fileName)
		self.workingList = []
		self.keyWords = _keyWords

	def report(self):
		print("-----------------------")
		print("Reporting on '{}'".format(self.fileName))
		for word in self.keyWords:
			item = self.logFile.logLineList.findFirst(word)
			item.print()
		print("-----------------------")

	def getMetrics(self, metricsSet):
		values = []
		for word in self.keyWords:
			item = self.logFile.logLineList.findFirst(word)
			if item is not None:
				values.append(item.timeStamp)
			else:
				print("Did not find {} ".format(word))
		metricsSet.appendSet(values)

	def keyWordReport(self, keyword):
		numItems = 0
		cumd = 0
		items = self.logFile.logLineList.find(keyword)
		for item in items:
			item.print()
			numItems += 1
			cumd += item.delta
		print("Num {} found = {}, Sum delay = {:.2f} ".format(keyword, numItems, cumd))

		for item in items:
			lineKeywords = item.text.split(" ")
			if (len(lineKeywords)>2):
				if lineKeywords[2] == "Service":
					tookIndex = item.text.find("took")
					if (tookIndex!=None):
						tookTime = item.text[tookIndex:tookIndex+10]
						print("{} took {}".format(lineKeywords[3], tookTime))


class Analyzer:
	def __init__(self):
		self.fileName = []

	def rebootAndRunCmdToFile(self, fileNamePrefix, msgPrefix, Cmd, numTimes, startIndex):
		captured = False
		error = False
		filenameNum = ""
		for i in range(numTimes):
			postfix = str(i+startIndex)
			filenameNum = fileNamePrefix + "-" + postfix + ".txt"
			print(msgPrefix + " to {}".format(filenameNum))
			# try 5 times to capure status 'boot_completed'
			for i in range(5):
				captured = False
				rebootCmd = "adb shell su root reboot"
				fullCmd = Cmd + " > {}".format(filenameNum)
				x = os.system(rebootCmd)
				if (x!=0):
					print("Error")
					error = True
					break
				time.sleep(45)
				x = os.system(fullCmd)
				if (x!=0):
					print("Error")
					error = True
					break
				# check for boot complete
				try:
					checkBootComplete = "grep boot_complete {}".format(filenameNum)
					output = subprocess.check_output(checkBootComplete, shell=True)
					captured = True
					break
				except:
					captured = False
					print("trying again for {}".format(filenameNum))
			if not captured:
				print("ERROR - failed to capture {}".format(filenameNum))
		if error:
			os.system("rm {}".format(filenameNum))
		return captured

	def getBuildID(self):
		buildIDCmd = "adb shell su root getprop ro.build.version.incremental"
		buildString = subprocess.check_output(buildIDCmd, shell = True)
		numberList = re.findall(r'\d+', buildString.decode('ISO-8859-1') )
		if (numberList==None): return 0
		if (len(numberList)==0): return 0
		buildID = numberList[0]
		return buildID

	def pullDmesgLogs(self, BuildID, numTimes, startIndex):
		fileNamePrefix = BuildID
		msgPrefix = "Pulling Kernel dmesg logs"
		cmd = "adb shell su root dmesg"
		return self.rebootAndRunCmdToFile(fileNamePrefix, msgPrefix, cmd, numTimes, startIndex)

	def pullLogcatLogs(self, BuildID, numTimes, startIndex):
		fileNamePrefix = "LC-"+BuildID
		msgPrefix = "Pulling Kernel Logcat"
		cmd = "adb logcat -b all -d"
		return self.rebootAndRunCmdToFile(fileNamePrefix, msgPrefix, cmd, numTimes, startIndex)

	def runBootAnalyze(self, filename, numTimes, startIndex):
		ABT = os.environ["ANDROID_BUILD_TOP"]
		if (len(ABT)<=0):
			print("ERROR - ANDROID_BUILD_TOP not set")
		BAFILE = "BA-" + filename + "-" + str(numTimes + startIndex) + ".txt"
		BACmd = ABT + "/system/extras/boottime_tools/bootanalyze/bootanalyze.py -c " + ABT + "/system/extras/boottime_tools/bootanalyze/config.yaml -n 20 -r -t > " + BAFILE
		print(BACmd)
		x = os.system(BACmd)
		if (x!=0):
			print("ERROR running bootanalze")
			return False
		return True

	def pullAll(self):
		BuildID = self.getBuildID()
		Cmd = "adb bugreport bugreport-{}".format(BuildID)
		print(Cmd)
		x = os.system(Cmd)
		if (x!=0):
			print("ERROR Pulling all data")
			return False
		self.pullDmesgLogs(BuildID, 20, 0)
		self.pullLogcatLogs(BuildID, 2, 0)
		self.runBootAnalyze(BuildID, 20, 0)
		self.summaryReportOnDmesgLogFiles(BuildID, 20)

	def summaryReportOnDmesgLogFiles(self, BuildID, numFiles):
		metricKeyWords = ["init first", "init second", "boot_completed"]
		metricSet = MetricSet(metricKeyWords)
		print("Summary report on log files with build ID {}".format(BuildID))
		dirList = glob.glob("{}*.txt".format(BuildID))
		numFilesAnalyzed = 0
		for index, file in enumerate(dirList):
			analyzeFile = AnalyzeFile(file, metricKeyWords)
			#check it's a kernel log file
			item = analyzeFile.logFile.logLineList.findFirst("build.fingerprint")
			if (item!=None):
				#check if it has the correct build ID
				if (item.text.find(BuildID)==-1):
					continue
			else:
				print("BuildID {} not found in file {} fingerprint {}".format(BuildID, file, item))
				continue
			analyzeFile.getMetrics(metricSet)
			numFilesAnalyzed += 1
			if ((index+1)>=numFiles):
				break
		if (numFilesAnalyzed>0):
			metricSet.analyze()
			metricSet.print()
		else:
			print("No files criteria {}* and build.fingerprint with {}".format(BuildID, BuildID))

	def rename(self, BuildID1, BuildID2, fileType):
		print("Summary report on log files with build ID {}".format(BuildID1))
		dirList = glob.glob("*{}*".format(BuildID1))
		for index, file in enumerate(dirList):
			findRes = file.find(BuildID1)
			if (findRes!=-1):
				newFile = file.replace(BuildID1, BuildID2, 1)
				newFile += fileType
				os.system("mv {} {}".format(file, newFile))


parser = argparse.ArgumentParser(description='pull all data files from seahawk and run dmesg summary report. The data files will be prefixed with the build ID')

parser.add_argument("-plc", nargs=3, metavar=('<BuildID>', '<numTimes>', '<startIndex>'),  help="pull logcat numTimes from seahawk")
parser.add_argument("-pdm", nargs=3, metavar=('<BuildID>', '<numTimes>', '<startIndex>'),  help="pull dmesg logs numTimes from seahawk")
parser.add_argument("-pba", nargs=2, metavar=('<BuildID>', '<numTimes>'),  help="pull bootanalyze numTimes from seahawk")
parser.add_argument("-rd", nargs=2, metavar=('<BuildID>', '<numFiles>'),  help="summary report on <numFiles> dmesg log files named <BuildID>-*.txt in current directory")
parser.add_argument("-pA", action='store_true', help="pull all data from seahawk a default number of times")
parser.add_argument("-t", nargs="*", help="test - do not use")
args = parser.parse_args()


if args.pdm!=None:
	Analyzer().pullDmesgLogs(args.pdm[0], int(args.pdm[1]), int(args.pdm[2]))

if args.plc!=None:
	Analyzer().pullLogcatLogs(args.plc[0], int(args.plc[1]), int(args.plc[2]))

if args.pba!=None:
	Analyzer().runBootAnalyze(args.pba[0], int(args.pba[1]), 0)

if args.pA!=None:
	Analyzer().pullAll()

if args.rd!=None:
	Analyzer().summaryReportOnDmesgLogFiles(args.rd[0], int(args.rd[1]))

if args.t!=None:
	Analyzer().getBuildID()

