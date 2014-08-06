#!/usr/bin/python
# programmer: beibei.chen@utsouthwestern.edu
# Usage: definition of alignment files including BED and BAM

import gzip

class BED:
	def __init__(self,chr,start,stop,name,score,strand):
		self.chr = chr
		self.start = start
		self.stop = stop
		self.name = name
		self.score = score
		self.strand = strand
	
	def __str__(self):
		st = "\t".join([self.chr,str(self.start),str(self.stop),self.name,str(self.score),self.strand])
		return st

	def merge(self,read):
		self.stop = read.stop
		self.score += 1

	def overlap(self,read):
		if self.chr == read.chr or self.strand == read.strand:
			if self.start <= read.stop and self.stop >=read.start:
				return True
			else:
				return False

class BAM:
	def __init__(self,filepath):
		self.filePath = filePath
		self.header = None
		self.sorted = None

	def checkHeader(self):
		'''Use gzip package to check if this is a bam or sam'''



