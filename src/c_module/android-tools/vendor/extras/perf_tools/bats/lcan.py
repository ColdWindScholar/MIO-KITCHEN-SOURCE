#!/usr/bin/python3
# -------------------------------------------
# logcat analysis
# -------------------------------------------
from ast import keyword
from curses import keyname
import argparse
import os
from string import digits
from sbtaTools import TextFile
import datetime
import re
import shlex
import glob

class LCItem:
	def __init__(self, lCTimeProcessor):
		self.dateTime = 0
		self.relativeTime = 0
		self.key = ""
		self.moduleName = ""
		self.keyword = ""
		self.valueMsec = 0
		self.lCTimeProcessor = lCTimeProcessor
		self.lines = []

	def set(self, dateTime, moduleName, keyText, valueMsec):
		try:
			self.dateTime = dateTime
			self.relativeTime = self.lCTimeProcessor.toRelativeTime(self.dateTime)
			self.moduleName = moduleName
			self.keyword = keyText
			self.key = moduleName+":" + keyText
			self.valueMsec = valueMsec
		except Exception as e:
			errLine = "LCItem:set() ERROR Failed: " + str(e)
			assert False, errLine

	def copy(self, otherLCItem):
		self.dateTime = otherLCItem.dataTime
		self.relativeTime = otherLCItem.relativeTime
		self.key = otherLCItem.key
		self.moduleName = otherLCItem.moduleName
		self.keyword = otherLCItem.keyword
		self.valueMsec = otherLCItem.valueMsec
		self.lCTimeProcessor = otherLCItem.lcTimeProcessor
		self.lines = otherLCItem.lines

	def appendLine(self, line):
		self.lines.append(line)

	def keyEqual(self, otherItem):
		if self.key != otherItem.key:
			return False
		return True

	def add(self, otherItem):
		assert(self.key==otherItem.key)
		self.lines.extend(otherItem.lines)
		self.valueMsec = self.valueMsec + otherItem.valueMsec
		return True

	def addValue(self, otherLCItem):
		if self.key=="":
			self.copy(otherLCItem)
		else:
			assert(self.key==otherLCItem.key)
			self.valueMsec = self.valueMsec + otherLCItem.valueMsec
		return True

	def divideValue(self, number):	# scaler divide
		self.valueMsec = self.valueMsec / number
		return True

	def key(self):
		return self.key

	def print(self):
		#systemTime = self.lCTimeProcessor.toSystemTime(self.dateTime)
		#relativeTime = self.lCTimeProcessor.toRelativeTime(self.dateTime)
		newTimeString = str(self.relativeTime)
		if (len(self.lines)>0):
			print("{} {}: {} {:.4f} - {}".format(newTimeString, self.moduleName, self.keyword, self.valueMsec, self.lines[0]))
		else:
			print("{} {}: {} {:.4f} -".format(newTimeString, self.moduleName, self.keyword, self.valueMsec))

	def printLines(self, prefix, min):
		if (len(self.lines)<min):
			return
		for line in self.lines:
			print("     {}{}".format(prefix, line))

	def findModuleName(self, lineTextWords):
		colonIndex = -1
		try:
			colonIndex = lineTextWords.index(":")
			# address case of colon with no space
			moduleName = lineTextWords[colonIndex-1]
		except:
			moduleName = ""
		if colonIndex==-1:
			for word in reversed(lineTextWords):
				index = word.find(":")
				if index!=-1:
					moduleName = word[:index]
					break
		moduleName = moduleName.strip()
		return colonIndex, moduleName

	def parseLineWithTook(self, line):
		maxLineLength = 100
		stage = 0
		try:
			words = line.split("  ")
			dataTimeO = self.lCTimeProcessor.parseTimeStamp(line)
			if line.find("took to complete") != -1:
				stage = 1
				tookIndex = line.find(" took to complete:")
				uptoEnd= line[:tookIndex]
				lineTextWords = uptoEnd.split()
				colonIndex, moduleName = self.findModuleName(lineTextWords)
				keyword  = " ".join([lineTextWords[6]])
				value = re.findall(r'\d+', line[tookIndex:])[-1]
				value = float(value)

			elif line.find("took") != -1:
				stage = 2
				tookIndex = line.find(" took")
				uptoEnd= line[:tookIndex]
				uptoBracket = uptoEnd.rfind("(")
				if uptoBracket != -1:
					uptoEnd = uptoEnd[:uptoBracket]
				#uptoEnd = uptoEnd.replace(":", "")
				lineTextWords = shlex.split(uptoEnd)
				colonIndex, moduleName = self.findModuleName(lineTextWords)
				# if there is colon only take words after it
				if colonIndex!=-1:
					lineTextWords = lineTextWords[colonIndex+1:]
				numWords = len(lineTextWords)
				keyword = ""
				stage = 3
				try:
					for i in range(max(numWords-3, 0), numWords, 1):
						keyword  = keyword + " " + lineTextWords[i]
				except Exception as e:
					errLine = "LCItem:parseLineWithTook() ERROR Failed to parse1: " + str(e)
					print(errLine)
					assert False, errLine

				# reduce length
				keyword = keyword[:maxLineLength]
				keyword = keyword.strip()
				# using regex expression to replace all numbers
				keyword = re.sub(r'\d', "_", keyword)
				value = 0
				stage = 4
				try:
					multplier = 1
					tookSubstring = line[tookIndex:]
					secondsIndex = tookSubstring.find("seconds")
					msIndex = tookSubstring.find("ms")
					if (secondsIndex!=-1):
						tookSubstring = tookSubstring[:secondsIndex]
						multiplier = 1000
					elif msIndex != -1:
						tookSubstring = tookSubstring[:msIndex]
					else:
						# known exception
						if tookSubstring.find("properties")==-1:
							errLine = "LCItem:parseLineWithTook() ERROR invalid took in substring 1B {}".format(line)
							print(errLine)
							assert False, errLine
							return False

					values = re.findall(r'[\d\.\d]+', tookSubstring)
					while "." in values:
						values.remove(".")
					value = float(values[-1])
					if line.find("seconds") != -1:
						value = value * multiplier
				except Exception as e:
					errLine = "LCItem:parseLineWithTook() ERROR Failed to parse2: " + str(e)
					print(errLine)
					assert False, errLine
				stage = 5

			else:
				return False

			stage = 6
			self.set(dataTimeO, moduleName, keyword, value)
			stage = 7
			self.lines.append(line)

			return True

		except Exception as e:
			errLine = "LCItem:parseLineWithTook() ERROR Failed to parse3:" + str(e)
			print(errLine, stage)
			assert False, errLine

	def parseLine(self, line):
		try:
			words = line.split("  ")
			dateTimeO = self.lCTimeProcessor.parseTimeStamp(line)
			if (dateTimeO!=None):
				#lcItem = LCItem(self.lCTimeProcessor)
				newLine = line[19:].rstrip()
				self.set(dateTimeO, "", newLine, 0)
				#self.print()
				return
			else:
				return None

		except Exception as e:
			errLine = "LCItem:parseLine() ERROR Failed to parse3:" + str(e)
			print(errLine)
			assert False, errLine

	def find(self, keyword):
		if self.key.find(keyword)!=-1:
			return True
		for line in self.lines:
			if line.find(keyword)!=-1:
				return True

	def createLogLine(self):
		line = ""
		msecs = self.dateTime.strftime("%f")
		timeString = self.dateTime.strftime("%m-%d %H:%M:%S.")
		#timeString = timeString + msecs[]
		return line

class LCItemSet:
	def __init__(self, item1, item2):
		self.item1 = item1
		self.item2 = item2
		if (item1.key != "" and item2.key != ""):
			assert(item1.key == item2.key)
		if (item1.key!=""):
			self.key = item1.key
		else:
			self.key = item2.key
		self.diff = item2.valueMsec - item1.valueMsec

	def __gt__(self, other):
			if(self.diff>other.diff):
				return True
			else:
				return False

	def add(item):
		assert(False)

	def print(self, min, printAll):
		self.diff = self.item2.valueMsec - self.item1.valueMsec
		if abs(self.diff)<min:
			return
		flag = "12"
		if self.item1.key=="":
			flag = "-2"

		if self.item2.key=="":
			flag = "1-"

		print("{}, {}, {}, {}, {}".format(self.key, self.item1.valueMsec, self.item2.valueMsec, self.diff, flag))
		if printAll:
			self.item1.printLines("1> ", 1)
			self.item2.printLines("2> ", 1)

class LCItemMap:
	def __init__(self):
		self.map = {}

	def put(self, newItem):
		item = self.map.get(newItem.key)
		if item==None:
			self.map[newItem.key] = newItem
		else:
			item.add(newItem)

	def print(self):
		for key in self.map:
			self.map[key].print()

	def find(self, keyword):
		lCItems = []
		for index, lCItem in self.map:
			if lCItem.find(keyword):
				lCItems.append(lCItem)
		return lCItems

	def addValues(self, other):
		for index, item in other.map.items():
			if item.key in self.map:
				self.map[item.key].addValue(item)
			else:
				self.map[item.key] = item

	def divideValue(self, number):
		for index, item in self.map:
			item.divideValue(number)

class LCItemSetMap:
	def __init__(self):
		self.map = {}

	def put(self, itemSet):
		item = self.map.get(itemSet.key)
		if item==None:
			self.map[itemSet.key] = itemSet
		else:
			item.add(itemSet)

	def printSorted(self, printAll):
		a = sorted(self.map.items(), key=lambda x: (x[1], x[0]), reverse=True)
		cumDif = 0
		print("Key, Value1, Value2, diff")
		for item in a:
			item[1].print(1, printAll)
			cumDif = cumDif + item[1].diff
		print("CUMULATIVE DIFF: {}".format(cumDif))

class LCTimeProcessor:
	def __init__(self):
		self.firstKernelTimeStamp = 0
		self.lastKernelTimeStamp = 0
		self.firstSystemTimesStamp = 0
		self.lastTimeStamp = 0
		self.zeroRelativeTime = 0
		today = datetime.datetime.now()
		year = str(today.year)
		self.currentYear = year[-2:] # 2022/2023

	def parseTimeStamp(self, line):
		try:
			if len(line)<19:
				return None
			currentYear = self.currentYear	# 22
			words = line.split("  ")
			timeString = words[0]
			#timeString = re.sub("[^0-9: -.]", "", timeString)
			timeString = timeString.strip()
			timeString = timeString[:18]
			timeString = currentYear + "-" + timeString
			dataTimeO = datetime.datetime.strptime(timeString, "%Y-%m-%d %H:%M:%S.%f")
			return dataTimeO
		except Exception as e:
			# If no time stamp on this line
			if line.find("beginning of")!=-1:
				return None
			errLine = "LCItem:parseTimeStamp() ERROR Failed to parse:" + str(e)
			print(errLine)
			assert False, errLine
			return None


	def process(self, line):
		timeStamp = self.parseTimeStamp(line)
		if timeStamp==None:
			return False

		if self.firstKernelTimeStamp==0:
			self.firstKernelTimeStamp = timeStamp
		else:
			if timeStamp < self.firstKernelTimeStamp:
				return False

			timeChange = timeStamp - self.lastTimeStamp
			if (timeChange.total_seconds() > 68*5):
				if self.firstSystemTimesStamp ==0:
					self.firstSystemTimesStamp = timeStamp
					self.lastKernelTimeStamp = self.lastTimeStamp
					self.zeroRelativeTime = self.toSystemTime(self.firstKernelTimeStamp)

		self.lastTimeStamp = timeStamp
		return True

	def toSystemTime(self, timeStamp):
		try:
			# if no systemTime is found, it must all be system time
			if self.firstSystemTimesStamp==0:
				self.firstSystemTimesStamp = self.firstKernelTimeStamp
				self.lastKernelTimeStamp = self.lastTimeStamp
				self.zeroRelativeTime = self.firstKernelTimeStamp
				return timeStamp
			if timeStamp >= self.firstSystemTimesStamp:
				return timeStamp
			else:
				timeChange = timeStamp - self.lastKernelTimeStamp
				systemTime = self.firstSystemTimesStamp + timeChange
				return systemTime
		except Exception as e:
			errLine = "LogLine:parseLine() ERROR Failed to parse3:" + str(e)
			print(errLine)
			assert False, errLine

	def toRelativeTime(self, timeStamp):
		systemTime = self.toSystemTime(timeStamp)
		relativeTime = systemTime - self.zeroRelativeTime
		return relativeTime

		if timeStamp< self.firstSystemTimesStamp:
			timeChange = timeStamp - self.lastKernelTimeStamp
			systemTime = self.firstSystemTimesStamp + timeChange
			return systemTime
		else:
			return timeStamp

	def toString(self, timeStamp):
		return timeStamp.strftime("%Y-%m-%d %H:%M:%S.%f")

class LCLogLine:
	def __init__(self, lCTimeProcessor):
		self.dateTime = 0
		self.relativeTime = 0
		self.lineText = ""
		self.lCTimeProcessor = lCTimeProcessor

	def set(self, dateTime, lineText):
		self.dateTime = dateTime
		self.relativeTime = self.lCTimeProcessor.toRelativeTime(self.dateTime)
		self.lineText = lineText

	def print(self):
		newTimeString = str(self.relativeTime)
		print("{}{}".format(newTimeString, self.lineText))

	def parseLine(self, line):
		try:
			dateTimeO = self.lCTimeProcessor.parseTimeStamp(line)
			if (dateTimeO!=None):
				lineText = line[19:].rstrip()
				self.set(dateTimeO, lineText)
				return
			else:
				return None

		except Exception as e:
			errLine = "LogLine:parseLine() ERROR Failed to parse3:" + str(e)
			print(errLine)
			assert False, errLine

	def find(self, word):
		if (self.lineText.find(word)!=-1):
			return True
		else:
			return False

	def findAll(self, words):
		for word in words:
			if (self.lineText.find(word)==-1):
				return False
		return True

class LCLogFile(TextFile):
	priorTimeStamp = 0.0
	def __init__(self, _fileName = ""):
		super(LCLogFile, self).__init__(_fileName)
		self.linesWithTook = []
		self.linesWithTookToComplete = []
		self.linesWithoutTookToComplete = []
		self.firstKernelTimeStamp = 0
		self.lastKernelTimeStamp = 0
		self.firstSystemTimesStamp = 0
		self.lastTimeStamp = 0
		self.lCTimeProcessor = LCTimeProcessor()
		self.dumpLinesBeforeBeginning()

	def dumpLinesBeforeBeginning(self):
		# start from --------- beginning of kernel
		beginningFound = False
		_lines = []
		for line in self.lines:
			if beginningFound==True:
				_lines.append(line)
				self.lCTimeProcessor.process(line)

			elif line.find("beginning of kernel") != -1:
				beginningFound = True

		self.lines = _lines


	def scanTook(self):
		lCItemMap = LCItemMap()
		foundBeginning = False
		for line in self.lines:
			# start at beginning
			if not foundBeginning:
				if line.find("beginning of kernel=1") != -1:
					foundBeginning = True
					continue

			# stop if boot complete
			if line.find("sys.boot_completed=1") != -1:
				break

			if line.find("took") != -1:
				self.linesWithTook.append(line.rstrip())

		for line in self.linesWithTook:
			lCItem = LCItem(self.lCTimeProcessor)
			if lCItem.parseLineWithTook(line)==True:
				lCItemMap.put(lCItem)

		return lCItemMap

	def print(self, numItems=None):
		self.scanTook()

	def convert(self, numItems=None):
		lcLogLines = []
		for line in self.lines:
			lcLogLine = LCLogLine(self.lCTimeProcessor)
			lcLogLine.parseLine(line)
			lcLogLines.append(lcLogLine)
		return lcLogLines
'''
	def createLCFile(self, fileName):
		# create LCTimeProcessor
		# create LCItem
		# create LCLogLine
		# write LCLogLine to file
'''
class ScanFile:
	def __init__(self):
		self.fileName = "none"

	def scanKeyWords(self, fileName):
		print("Scanning {}".format(fileName))
		cmd = "grep \"apexd: wait for '\/dev\/loop-control'\" {}".format(fileName)
		x = os.system(cmd)
		cmd = "grep \"Service 'apexd-bootstrap\" {}".format(fileName)
		x = os.system(cmd)
		cmd = "grep apexd.status=activated {}".format(fileName)
		x = os.system(cmd)
		cmd = "grep \"Service 'bpfloader'\" {}".format(fileName)
		x = os.system(cmd)
		cmd = "grep \"sys.boot_completed=1\" {} | head -n 1".format(fileName)
		x = os.system(cmd)

	def scanTook(self, fileName):
		lCLogFile = LCLogFile(fileName)
		lCItemMap = lCLogFile.scanTook()

	def convert(self, fileName):
		lCLogFile = LCLogFile(fileName)
		lcItems = lCLogFile.convert()
		for lcItem in lcItems:
			lcItem.print()

	def phases(self, fileName):
		keywordFile = TextFile("keywords")
		#keywords = ['init first', 'init second', "Starting phase 200", "boot_completed"]

		lCLogFile = LCLogFile(fileName)
		keywordSets = []
		for line in keywordFile.lines:
			line = line.strip()
			keywordSet = line.split(", ")
			keywordSets.append(keywordSet)

		lcLogLines = lCLogFile.convert()
		for keywordSet in keywordSets:
			for lcLogLine in lcLogLines:
				if lcLogLine.findAll(keywordSet)==True:
					lcLogLine.print()
					break

class Compare:
	def __init__(self):
		self.fileName = "none"

	def compareLCItemMaps(self, lCItemMap1, lCItemMap2):
		lCItemSetMap = LCItemSetMap()

		for item1key in lCItemMap1.map:
			found = False
			for item2key in lCItemMap2.map:
				if item2key==item1key:
					lcItemSet = LCItemSet(lCItemMap1.map[item1key], lCItemMap2.map[item2key])
					lCItemSetMap.put(lcItemSet)
					found = True
					break
			# if item1Key is not in ItemMap2, add a null item
			if found==False:
				lCTimeProcessor = LCTimeProcessor()
				nullLCItem = LCItem(lCTimeProcessor)
				lcItemSet = LCItemSet(nullLCItem, lCItemMap1.map[item1key])
				lCItemSetMap.put(lcItemSet)
				found = True

		lCItemSetMap.printSorted(printAll)
		return lCItemSetMap

	def compareFiles(self, fileName1, fileName2, printAll):
		print("---------------------------------------------------------------")
		print("lcan.py -cmp {} {}".format(fileName1, fileName2))
		print("---------------------------------------------------------------")
		lCLogFile1 = LCLogFile(fileName1)
		lCItemMap1 = lCLogFile1.scanTook()
		lCLogFile2 = LCLogFile(fileName2)
		lCItemMap2 = lCLogFile2.scanTook()

		lCItemSetMap = LCItemSetMap()

		for item1key in lCItemMap1.map:
			found = False
			for item2key in lCItemMap2.map:
				if item2key==item1key:
					lcItemSet = LCItemSet(lCItemMap1.map[item1key], lCItemMap2.map[item2key])
					lCItemSetMap.put(lcItemSet)
					found = True
					break
			# if item1Key is not in ItemMap2, add a null item
			if found==False:
				lCTimeProcessor = LCTimeProcessor()
				nullLCItem = LCItem(lCTimeProcessor)
				lcItemSet = LCItemSet(nullLCItem, lCItemMap1.map[item1key])
				lCItemSetMap.put(lcItemSet)
				found = True

		lCItemSetMap.printSorted(printAll)
		return lCItemSetMap

	def getAverageOfDir(self, buildId):
		#get average values for build1
		dirList = glob.glob("{}/LC-{}*.txt".format(buildId, buildId))
		numFiles = len(dirList)
		#iterate in numerical order
		lCItemMapS = LCItemMap()
		for index in range(numFiles):
			fileName = "{}/LC-{}-{}.txt".format(buildId, buildId, index)
		#for index, fileName in enumerate(dirList):
			lCLogFile = LCLogFile(fileName)
			lCItemMap = lCLogFile.scanTook()
			lCItemMapS.addValues(lCItemMap)
		lCItemMapS.divideValue(numFiles)
		return lCItemMapS

	def compareDirs(self, buildId1, buildId2, printAll):
		print("---------------------------------------------------------------")
		print("lcan.py -cmpd {} {} {}".format(buildId1, buildId2, printAll))
		print("---------------------------------------------------------------")

		#get average values for build1
		lCItemMap1 = self.getAverageOfDir(buildId1)
		lCItemMap2 = self.getAverageOfDir(buildId2)
		self.compareLCItemMaps(self, lCItemMap1, lCItemMap2)


parser = argparse.ArgumentParser()
parser.add_argument("-c", nargs=1, metavar=('<fileName>'), help="convert Logcat output to start from boot with converted timeStamps")
parser.add_argument("-k", nargs=1, metavar=('<fileName>'), help="summary on keywords")
parser.add_argument("-a", nargs=1, metavar=('<fileName>'), help="analyze file")
parser.add_argument("-cmp", nargs=3, metavar=('<fileName1>', '<fileName2>', '<brief/all>'), help="compare logcat files")
parser.add_argument("-cmpd", nargs=3, metavar=('<dirName1>', '<dirName2>', '<brief/all>'), help="compare logcat files")
parser.add_argument("-p", nargs=1, metavar=('<fileName1>'), help="phase report on log files")
args = parser.parse_args()

if args.k!=None:
	scanFile = ScanFile()
	scanFile.scanKeyWords(args.k[0])

if args.a!=None:
	scanFile = ScanFile()
	scanFile.scanTook(args.a[0])

if args.c!=None:
	scanFile = ScanFile()
	scanFile.convert(args.c[0])

if args.p!=None:
	scanFile = ScanFile()
	scanFile.phases(args.p[0])

if args.cmp!=None:
	printAll = False
	compare = Compare()
	if (len(args.cmp)>2):
		if (args.cmp[2].find("all")!=-1):
			printAll = True
	compare.compareFiles(args.cmp[0], args.cmp[1], printAll)

if args.cmpd!=None:
	printAll = False
	compare = Compare()
	if (len(args.cmpd)>2):
		if (args.cmpd[2].find("all")!=-1):
			printAll = True
	compare.compareDirs(args.cmpd[0], args.cmpd[1], printAll)
