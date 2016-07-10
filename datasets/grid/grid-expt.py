import sys
try:
    import networkx
    import matplotlib.pyplot as plt
    NETWORKX = True
except Exception:
    print 'no networkx'
    NETWORKX = False
import numpy as NP
import random
import math
import time

import declare
import matrixdb
import dataset
import tensorlog
import funs
import ops
import expt
import mutil
import learn
 
def nodeName(i,j): 
    return '%d,%d' % (i,j)

def visualizeLearned(db,n):
    m = db.getParameter('edge',2)
    g = networkx.DiGraph()
    weight = {}
    #look at all edges downward
    for i in range(1,n+1):
        for j in range(1,n+1):
            src = nodeName(i,j)
            for di in [-1,0,+1]:
                for dj in [-1,0,+1]:
                    if (1 <= i+di <= n) and (1 <= j+dj <= n):
                        dst = nodeName(i+di,j+dj)
                        wTo = m[db.stab.getId(src),db.stab.getId(dst)]
                        wFrom = m[db.stab.getId(dst),db.stab.getId(src)]
                        if wTo>wFrom:
                            weight[(src,dst)] = wTo-wFrom
                            g.add_edge(src,dst,weight=weight[(src,dst)])
                        else:
                            weight[(dst,src)] = wFrom-wTo
                            g.add_edge(dst,src,weight=weight[(dst,src)])
                            
                            #print "weight %s -> %s" % (src,dst),m[db.stab.getId(src),db.stab.getId(dst)]

    #color the edges with 10 different int values
#    maxw = max(weight.values())
#    minw = min(weight.values())
#    def colorCode(w):
#        return round(10 * (w-minw) / (maxw-minw))
    weightList = sorted(weight.values())
    def colorCode(w):
        return round(10*float(weightList.index(w))/len(weightList))
    edgeColors = map(lambda e:colorCode(weight.get(e,0)), g.edges())
        
    pos = {}
    #position the nodes
    for i in range(n+1):
        for j in range(n+1):
            src = nodeName(i,j)
            pos[src] = NP.array([i/(n+1.0),j/(n+1.0)])
    edgeList = g.edges()

    #networkx.draw(g,pos,node_color='#A0CBE2',edge_color=colors,width=4,edge_cmap=plt.cm.Blues,with_labels=False)
    networkx.draw(g,pos,node_color='#A0CBE2',width=4,edge_color=edgeColors,edge_cmap=plt.cm.cool,
                  with_labels=True,node_size=400)
    plt.savefig("visualize.png") # save as png
    #plt.show() # display                        

def generateGrid(n,outf):
    fp = open(outf,'w')
    for i in range(1,n+1):
        for j in range(1,n+1):
            for di in [-1,0,+1]:
                for dj in [-1,0,+1]:
                    if (1 <= i+di <= n) and (1 <= j+dj <= n):
                        fp.write('edge\t%s\t%s\t0.5\n' % (nodeName(i,j),nodeName(i+di,j+dj)))

def generateData(n,trainFile,testFile):
    fpTrain = open(trainFile,'w')
    fpTest = open(testFile,'w')
    r = random.Random()
    for i in range(1,n+1):
        for j in range(1,n+1):
            #target
            ti = 1 if i<n/2 else n
            tj = 1 if j<n/2 else n
            x = nodeName(i,j)
            y = nodeName(ti,tj)
            fp = fpTrain if r.random()<0.67 else fpTest
            fp.write('\t'.join(['path',x,y]) + '\n')

if __name__=="__main__":

    # usage: acc [grid-size] [maxDepth] [epochs]"
    #        time [grid-size] [maxDepth] "

    goal = 'acc'
    if len(sys.argv)>1:
        goal = sys.argv[1]
    n = 6
    if len(sys.argv)>2:
        n = int(sys.argv[2])
    maxD = round(n/2.0)
    if len(sys.argv)>3:    
        maxD = int(sys.argv[3])
    epochs = 20
    if len(sys.argv)>4:
        epochs = int(sys.argv[4])

    #generate grid
    stem = 'g%d' % n

    factFile = stem+'.cfacts'
    trainFile = stem+'-train.exam'
    testFile = stem+'-test.exam'

    generateGrid(n,factFile)
    generateData(n,trainFile,testFile)

    db = matrixdb.MatrixDB.loadFile(factFile)
    prog = tensorlog.Program.loadRules("grid.ppr",db)

    startNode = nodeName(1,1)
    if goal=='time':
        for d in [4,8,16,32,64,99]:
            print 'depth',d,
            ti = tensorlog.Interp(prog)
            ti.prog.maxDepth = d
            start = time.time()
            ti.prog.evalSymbols(declare.asMode("path/io"), [startNode])
            print 'time',time.time() - start,'sec'


    elif goal=='acc':
        print 'grid-acc-expt: %d x %d grid, %d epochs, maxPath %d' % (n,n,epochs,maxD)

        trainData = dataset.Dataset.loadExamples(db,trainFile)
        testData = dataset.Dataset.loadExamples(db,testFile)
        prog.db.markAsParam('edge',2)

        params = {'prog':prog,
                  'trainData':trainData, 'testData':testData,
                  'savedTestPredictions':'tmp-cache/test.solutions.txt',
                  'savedTestExamples':'tmp-cache/test.examples',
                  'learner':learn.FixedRateGDLearner(
                      prog,
                      regularizer=learn.L2Regularizer(0.1),
                      epochs=epochs,
                      rate=0.01,
                      )}
        prog.maxDepth = maxD
        NP.seterr(divide='raise')

        #prog.normalize = 'log+softmax'
        #funs.conf.trace = True
        #ops.conf.trace = True
        #ops.conf.long_trace = True
        ops.conf.max_trace = True
        expt.Expt(params).run()
        if NETWORKX:
            visualizeLearned(db,n)

