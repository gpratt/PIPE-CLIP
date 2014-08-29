#!/usr/bin/python
# Programmer : beibei.chen@utsouthwestern.edu
# Usage: Get reliable mutations using binomial distribution
# Input: Filtered BAM, reads coverage (generated by SAMFilter.py), mutation file
# Output: BED 
# Last modified: 19 Dec.2013


import sys
import re
import random
import string
import pysam
from pysam import *
import argparse as ap
from pybedtools import BedTool
import copy
import rpy2.robjects as robject
from rpy2.robjects.packages import importr
from rpy2.robjects import FloatVector
import math
from collections import Counter
import pandas as pd

stats = importr('stats')
mass = importr('MASS')
vgam = importr('VGAM')


def muEvaluate(self,mapfile,mufile,cover,threshold):
  (original_KM,KM_test) = self.KMvalue(mapfile,mufile)
  R = robject.r
  reliableList = []
  P = len(mufile)/(cover*1.0)
  km_p = {}#store km and corresponding p value
  pvalues = []
  for k in KM_test:
    parameters = k.split("_")
    p = R.pbinom(int(parameters[1])-1,int(parameters[0]),P,False)[0]  
    pvalues.append(p)
    km_p[k]=p

def mutationFilterMainNoArgs():
  try:
    infile = pandas.read_table(sys.argv[1],sep="\t").values
  except IOError,message:
    print >> sys.stderr, "cannot open coverage file",message
    sys.exit(1)
  cluster_len = infile[:,2]-infile[:,1]
  print cluster_len
  
  
if __name__=="__main__":
  mutationfilterMainNoArgs()