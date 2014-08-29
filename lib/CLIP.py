'''Define CLIP class'''
import sys
import gzip
import copy
import logging
import pysam
import random
import Utils
import Alignment
import Mutation2
import OptValidator

OptValidator.opt_validate()


class CLIP:
	def __init__(self,fileaddr):
		self.filepath = fileaddr
		self.originalBAM = None
		self.filteredAlignment = []
		self.type = 0
		self.currentGroupKey = "None"
		self.currentGroup = [] #Used in rmdup
		self.previousQul = [0,0,0]#for rmdup,[matchlen,mapq,mismatch]
		self.clusters = [] 
		self.currentCluster = Alignment.BED("",0,0,"",0,".")
		#self.sigClusters = {}
		self.mutations = {} #Dictionary of bed instance
		self.mutationCount = 0
		self.sigMutations = {}#same as sigClusters
		self.sigMutationCount = 0
		self.sigClusterCount = 0
		self.wig = None
		self.coverage = 0 #"reads coverage of this sample"
		self.bamheader = None
		self.crosslinking = {}
		self.crosslinkingMutations = []

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
				logging.error("Input file does not have header, please check your file. Program quit")
				return (False,"None")
		#Header test passed, test if it is BAM
		try:
			infile = gzip.open(self.filepath)
			infile.readline(10)
		except:#cannot read line, should be sam
			logging.info("Input is SAM, converting to BAM...")
			bamout = ".".join(self.filepath.split(".")[0:-1])+"."+"bam"
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
			logging.info("Input is not sorted, sorting file...")
			bamsort = ".".join(self.filepath.split(".")[0:-1])+"."+"sort"
			pysam.sort(self.filepath,bamsort)
			pysam.index(bamsort+".bam")
			self.filepath = bamsort+".bam" # change input file path
			self.header = pysam.view("-H",bamsort+".bam")
			logging.info("Input file sorted")
			#if Utils.is_sorted(self.header):
			#	print >> sys.stderr, "The file is sorted"
			return True
			
	def readfile(self):
		try:
			self.originalBAM = pysam.Samfile(self.filepath,"rb")
			return True
		except IOError,message:
			logging.error("Cannot open input file"+message)
			return False

	def printFilteredReads(self):
		for i in self.filteredAlignment:
			print i
	
	def printClusters(self):
		for i in self.clusters:
			print i

	def printMutations(self):
		for i in self.mutations.values():
			print i

	def printReliableMutations(self):
		for i in self.mutations.values():
			if i.sig:
				st = i.__str__()
				st += "\t"+str(i.pvalue)+"\t"+str(i.qvalue)
				print st

	def printEnrichedItem(self,dic):
		for k in dic.keys():
			print k
			for i in dic[k]:
				st = i.__str__()
				st += "\t"+str(i.pvalue)+"\t"+str(i.qvalue)
				print st
	
	def printCrosslinkingSites(self):
		for i in self.crosslinking.values():
			st = i.__str__()
			st += "\t"+"\t".join([str(i.qvalue),str(i.fisherP)])
			st += "\t"+",".join(i.mutationStarts)
			st += "\t"+",".join(i.mutationNames)


	def updatePreviousQul(self,n,q,m):
		self.previousQul[0] = n
		self.previousQul[1] = q
		self.previousQul[2] = m
	

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
		self.currentGroup = [read]
		self.updatePreviousQul(mlength,read.mapq,mismatch)

	def rmdup(self):
		'''Return random one read of highest quality from list'''
		#print "get one from group"
		if len(self.currentGroup)==1:
			#print self.currentGroup[0]
			return self.currentGroup[0]
		else:
			random.seed(1)
			index = random.randint(0,len(self.currentGroup)-1)
			#print self.currentGroup[index]
			return self.currentGroup[index]

	def updateCluster(self,read):
		'''Cluster new read to known clusters and update cluster reads count'''
		strandDic = {"True":"-","False":"+"}
		clusterName = "cluster"+"_"+str(len(self.clusters)+1)
		newRead = Alignment.ClusterBed(self.originalBAM.getrname(read.tid),read.pos,read.pos+len(read.seq),clusterName,1,strandDic[str(read.is_reverse)])
		if self.currentCluster.chr == "": #Initiate cluster
			self.currentCluster = newRead
			self.clusters.append(self.currentCluster)
		else:
			if self.currentCluster.overlap(newRead):
				self.currentCluster.merge(newRead)
				self.clusters[-1]=self.currentCluster
			else:#New read is a new cluster
				#self.clusters.append(self.currentCluster)
				self.currentCluster = newRead
				self.clusters.append(self.currentCluster)
	
	def updateMutation(self,read,mis):
		
		if self.type == 3:#iclip,find truncation
			mutations = Mutation2.getTruncations(self.originalBAM,read)
		else:
			if mis > 0:
				mutations = Mutation2.getMutations(self.originalBAM,read)
				if self.type ==1:
					mutation_filter = Utils.filterMutation(mlist,"T->C",True)
				elif self.type ==2:
					mutation_filter = Utils.filterMutation(mlist,"G->A",True)
				mutations = mutation_filter
			else:
				mutation = []
		if len(mutations)>0:
			for m in mutations:
				#print m
				self.mutationCount += 1
				m_key = "_".join([m.chr,str(m.start),m.strand,m.type])
				if self.mutations.has_key(m_key):
					self.mutations[m_key].increaseScore()
				else:
					self.mutations[m_key]=m

	def updateCLIPinfo(self,read,matchlen,miscount):
		'''Update sample coverage info, clustering, mutation info'''
		#update sample coverage info
		self.coverage += matchlen
		#update cluster info
		self.updateCluster(read)
		#update mutation info
		self.updateMutation(read,miscount)

	def addSigToDic(self,dic,mu):
		'''Add new mutation into the dictionary.Mutations should be sorted'''
		if dic.has_key(mu.chr):
			dic[mu.chr].append(mu)
		else:
			dic[mu.chr] = [mu]
	
	def getCrosslinking(self):
		'''Merge enriched clusters and reliable mutations together
				Call Enrich.fisherTest() to calculate joint p vlaue
		'''
		for cluster in self.clusters:
			#logging.debug("P value of cluster is %f" % cluster.pvalue)
			if cluster.sig and self.sigMutations.has_key(cluster.chr):
				for mutation in self.sigMutations[cluster.chr]:
					if cluster.overlap(mutation):
						if self.type == 0:#HITS-CLIP
							mutation_key = mutation.type.split("->")[0]
							if mutation_key in ["A","C","G","T"]:
								mutation_key = "Substitution"
							cross_key = cluster.name+"_"+mutation_key
						else:
							cross_key = cluster.name
						if self.crosslinking.has_key(cross_key):
							#logging.debug("Existing mutation pvalue:",self.crosslinking[cluster.name].mutationP)
							self.crosslinking[cross_key].addMutation(mutation)
							self.crosslinkingMutations.append(mutation)
						else:
							self.crosslinking[cross_key] = Alignment.CrosslinkingBed(cluster.chr,cluster.start,cluster.stop,cluster.name,cluster.score,cluster.strand,cluster.pvalue,cluster.qvalue,mutation.start,mutation.name,mutation.pvalue)
		#start to calculate fisher test p value
		for k in self.crosslinking.keys():
			self.crosslinking[k].fishertest()




	def filter(self,matchLen,mismatch,cliptype,duprm):
		'''Filter the input BAM file according to parameters. Make clusters and mutations at the same time'''
		logging.info("Start to filter alignment using parameters:")
		logging.debug("match length:%d" % (matchLen))
		logging.debug("CLIP type:%s" % (str(cliptype)))
		logging.debug("Rmdup code:%s" % (str(duprm)))
		logging.debug("There are %d reads in origianl input file" % (self.originalBAM.mapped))
		self.type = cliptype
		if cliptype == 3:#make sure there is no rmdup for iCLIP data
			duprm = 0
		count = 0
		for alignment in self.originalBAM:
			#print "Now processing",alignment.qname
			count += 1
			if count % 100000 ==0:
				logging.debug("Processed %d reads." % count)
			flag,mlen,mis = Utils.readQuaFilter(alignment,matchLen,mismatch)
			if flag:
				#print "Qualified read"
				#print	alignment
				#print "current Gourp key",self.currentGroupKey
				if duprm > 0:
					if duprm == 1:
						groupkey = Utils.rmdupKey_Start(alignment)
					elif duprm == 2:
						groupkey = Utils.rmdupKey_Seq(alignment)
					if groupkey == self.currentGroupKey:
						self.updateCurrentGroup(alignment,mlen,mis)
					else:
						if self.currentGroupKey!="None":#there are reads in current group
							keep = self.rmdup()
							self.currentGroup = []
							self.filteredAlignment.append(keep)
							self.updateCLIPinfo(keep,mlen,mis)
						self.iniDupGroupInfo(alignment,groupkey,mlen,mis)
				else:#there is no rmdup
					self.filteredAlignment.append(alignment)
					self.updateCLIPinfo(alignment,mlen,mis)
		#clean up the final dupGroup
		if len(self.currentGroup)>0:
			keep = self.rmdup()
			self.currentGroup = []
			self.filteredAlignment.append(keep)
			self.updateCLIPinfo(keep,mlen,mis)

		#Logging CLIP sample information
		logging.debug("After filtering, %d reads left" % (len(self.filteredAlignment)))
		logging.debug("There are %d clusters in total" % (len(self.clusters)))
		logging.debug("There are %d mutations in total" % (len(self.mutations)))

		

