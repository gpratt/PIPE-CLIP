'''Define CLIP class'''
import sys
import gzip
import logging
import pysam
import random
import Utils


class CLIP:
	def __init__(self,fileaddr):
		self.filepath = fileaddr
		self.originalBAM = None
		self.filteredAlignment = []
		self.currentGroupKey = "None"
		self.currentGroup = [] #Used in rmdup
		self.previousQul = [0,0,0]#for rmdup,[matchlen,mapq,mismatch]
		self.clusters = {} #Dictionary of bed instance
		self.mutations = {} #Dictionary of bed instance
		self.wig = None
		self.coverage = 0 #"reads coverage of this sample"
		self.bamheader = None
	
	def __str__(self):
		pass

	def testInput(self):
		'''Test the input file format, modify self.filepath and return bool
		Status: True:file is ready to use; False: wrong file, program stop
		'''
		#test if file has header
		try:
			self.header = pysam.view("-H",self.filepath)
		except:
			try:
				self.header = pysam.view("-SH",self.filepath)
			except:
				print >> sys.stderr, "Input file does not have header, please check your file. Program quit"
				return (False,"None")
		#Header test passed, test if it is BAM
		try:
			infile = gzip.open(self.filepath)
			infile.readline(10)
		except:#cannot read line, should be sam
			print >> sys.stderr,"Input is SAM, converting to BAM...",
			bamout = ".".join(self.filepath.split(".")[0:-1])+"."+"bam"
			print >> sys.stderr,bamout
			infile = pysam.Samfile(self.filepath,"r",header=self.header)
			#print >> sys.stderr,pysam.view("-SH",infile)
			outfile = pysam.Samfile(bamout,"wb",template=infile)
			for i in infile.fetch():
				outfile.write(i)
			self.filepath = bamout
		#Now the infile is BAM,check if it is sorted
		if Utils.is_sorted(self.header):
			pysam.index(self.filepath)
			return True
		else:#sort the BAM
			print >> sys.stderr, "Input is not sorted, sorting file..."
			bamsort = ".".join(self.filepath.split(".")[0:-1])+"."+"sort"
			pysam.sort(self.filepath,bamsort)
			pysam.index(bamsort+".bam")
			self.filepath = bamsort+".bam" # change input file path
			self.header = pysam.view("-H",bamsort+".bam")
			print >> sys.stderr,self.header
			#if Utils.is_sorted(self.header):
			#	print >> sys.stderr, "The file is sorted"
			return True
			
	def readfile(self):
		try:
			self.originalBAM = pysam.Samfile(self.filepath,"rb")
		except IOError,message:
			print >> sys.stderr, "Cannot open input file",message
			return False
	
	def updatePreviousQul(self,n,q,m):
		self.previoutQul[0] = n
		self.previoutQul[1] = q
		self.previoutQul[2] = m
	

	def updateCurrentGroup(self,read,mlen,mis):
		'''Compare read to current duplication group parameters, determine to add to, to drop or to replace, make sure duplication group only has reads with best quality'''
		if mlen >= self.previousQul[0] and read.mapq >= self.previousQul[1] and mis <= self.previousQul[2]:# consider to append or replace only when read has no worse quality
			if mlen > self.previousQul[0] or read.mapq > self.previousQul[1] or mis < self.previousQul[2]:# read has better quality,replace
				self.currentGroup = [read]
				self.updatePreviousQul(mlen,read.mapq,mis)
			else:
				self.currentGroup.append(read)
	
	def iniDupGroupInfo(self,read,group_key,mlength,mismatch):
		self.currentGroupKey = group_key
		self.currentGroup.append(read)
		self.updatePreviousQul(mlength,read.mapq,mismatch)

	def rmdup(self):
		'''Return random one read of highest quality from list'''
		if len(self.currentGroup)==1:
			return self.currentGroup[0]
		else:
			random.seed(1)
			index = random.randint(0,len(self.currentGroup)-1)
			return self.currentGroup[index]

	def updateCLIPinfo(self):
		pass



	def filter(self,matchLen,mismatch,cliptype,duprm):
		for alignment in self.originalBAM:
			flag,mlen,mis = Utils.readQuaFilter(alignment,matchLen,mismatch)
			if flag:
				if duprm > 0:
					if duprm == 1:
						groupkey = Utils.rmdupKey_Start(alignment)
					elif duprm == 2:
						groupkey = Utils.rmdupKey_Seq(alignment)
					if groupkey == self.currentGroupKey:
						self.updateCurrentGroup(alignment,mlen,mis)
					else:
						if self.currentGroupKey!="None":
							keep = self.rmdup()
							self.filteredAlignment.append(keep)
							self.updateCLIPinfo(keep,mlen)
						self.iniDupGroupInfo(alignment,groupkey,mlen,mis)
				else:
					self.updateCLIPinfo(alignment,mlen)
		#clean up the final dupGroup

