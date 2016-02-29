# (C) William W. Cohen and Carnegie Mellon University, 2016

import unittest
import logging
import sys

import scipy.sparse

import tensorlog 
import parser
import matrixdb
import bpcompiler
import ops

TEST_GRADIENTS = False

# can call a single test with, e.g.,
# python -m unittest testtensorlog.TestSmallProofs.testIf

class TestSmallProofs(unittest.TestCase):
    
    def setUp(self):
        self.db = matrixdb.MatrixDB.loadFile('test/fam.cfacts')
    
    def testIf(self):
        self.inferenceCheck(['p(X,Y):-spouse(X,Y).'], 'p(i,o)', 'william', {'susan':1.0})

    def testOr(self):
        self.inferenceCheck(['p(X,Y):-spouse(X,Y).', 'p(X,Y):-sister(X,Y).'], 'p(i,o)', 'william', 
                            {'susan':1.0, 'rachel':1.0, 'lottie':1.0, 'sarah':1.0})

    def testChain(self):
        self.inferenceCheck(['p(X,Z):-spouse(X,Y),sister(Y,Z).'], 'p(i,o)', 'susan', 
                            {'rachel':1.0, 'lottie':1.0, 'sarah':1.0})

    def testMid(self):
        self.inferenceCheck(['p(X,Y):-sister(X,Y),child(Y,Z).'], 'p(i,o)', 'william', 
                            {'sarah': 1.0, 'rachel': 2.0, 'lottie': 2.0})

    def testNest(self):
        self.inferenceCheck(['s(X,Y):-spouse(X,Y).','t(X,Z):-spouse(X,Y),s(Y,Z).'], 't(i,o)', 'susan', {'susan': 1.0}) 

    def testBack1(self):
        self.inferenceCheck(['p(X,Y):-spouse(X,Y),sister(X,Z).'], 'p(i,o)', 'william', {'susan': 3.0})

    def testBack2(self):
        self.inferenceCheck(['p(X,Y):-spouse(X,Y),sister(X,Z1),sister(X,Z2).'],'p(i,o)','william',{'susan': 9.0})

    def testRec1(self):
        tensorlog.MAXDEPTH=4
        self.inferenceCheck(['p(X,Y):-spouse(X,Y).','p(X,Y):-p(Y,X).'], 'p(i,o)','william',{'susan': 5.0})
        tensorlog.MAXDEPTH=10
        self.inferenceCheck(['p(X,Y):-spouse(X,Y).','p(X,Y):-p(Y,X).'], 'p(i,o)','william',{'susan': 11.0})

    def testConstOutput(self):
        self.inferenceCheck(['sis(X,W):-set(W,william),child(X,Y).'], 'sis(i,o)', 'sarah', {'william': 1.0})
        self.inferenceCheck(['sis(X,W):-set(W,william),child(X,Y).'], 'sis(i,o)', 'lottie', {'william': 2.0})

#    def testTrivConstOutput(self):
#        self.inferenceCheck(['sis(X,W):-set(W,william).'], 'sis(i,o)', 'sarah', {'william': 1.0})
#        self.inferenceCheck(['sis(X,W):-set(W,william).'], 'sis(i,o)', 'lottie', {'william': 1.0})

    def testConstChain1(self):
        self.inferenceCheck(['p(X,S) :- set(S,susan),sister(X,Y),child(Y,Z).'],'p(i,o)','william',{'susan': 5.0})

    def testConstChain2(self):
        #self.inferenceCheck(['p(X,Pos) :- set(Pos,pos),child(X,Y),young(Y).'],'p(i,o)','rachel',{'pos':0.0})
        self.inferenceCheck(['p(X,Pos) :- set(Pos,pos),child(X,Y),young(Y).'],'p(i,o)','sarah',{'pos':1.0})
        self.inferenceCheck(['p(X,Pos) :- set(Pos,pos),child(X,Y),young(Y).'],'p(i,o)','lottie',{'pos':2.0})

    def testAltChain(self):
        self.inferenceCheck(['p(X,W) :- spouse(X,W),sister(X,Y),child(Y,Z).'],'p(i,o)','william',{'susan': 5.0})

    def testProppr1(self):
        w = 7*self.db.onehot('r1')+3*self.db.onehot('r2')        
        self.propprInferenceCheck(w,['p(X,Y):-sister(X,Y) {r1}.','p(X,Y):-spouse(X,Y) {r2}.'],'p(i,o)',
                                  'william', {'sarah': 7.0, 'rachel': 7.0, 'lottie': 7.0, 'susan': 3.0})

    # support routines
    # 

    def maybeNormalize(self,expectedResultDict):
        if bpcompiler.NORMALIZE:
            norm = sum(expectedResultDict.values())
            for c in expectedResultDict:
                expectedResultDict[c] /= norm


    def inferenceCheck(self,ruleStrings,modeString,inputSymbol,expectedResultDict):
        print 'testing inference for mode',modeString,'on input',inputSymbol,'with rules:'
        self.maybeNormalize(expectedResultDict)
        for r in ruleStrings:
            print '>',r
        rules = parser.RuleCollection()
        for r in ruleStrings:
            rules.add(parser.Parser.parseRule(r))
        prog = tensorlog.Program(db=self.db,rules=rules)
        mode = tensorlog.ModeDeclaration(modeString)
        fun = prog.compile(mode)
        y1 = prog.evalSymbols(mode,[inputSymbol]) 
        self.checkDicts(self.db.rowAsSymbolDict(y1), expectedResultDict)


    def propprInferenceCheck(self,weightVec,ruleStrings,modeString,inputSymbol,expectedResultDict):
        print 'testing inference for mode',modeString,'on input',inputSymbol,'with proppr rules:'
        self.maybeNormalize(expectedResultDict)
        rules = parser.RuleCollection()
        for r in ruleStrings:
            rules.add(parser.Parser.parseRule(r))
        prog = tensorlog.ProPPRProgram(db=self.db,rules=rules,weights=weightVec)
        mode = tensorlog.ModeDeclaration(modeString)
        fun = prog.compile(mode)

        y1 = prog.evalSymbols(mode,[inputSymbol]) 
        self.checkDicts(self.db.rowAsSymbolDict(y1), expectedResultDict)

        gd = prog.evalGradSymbols(mode,[inputSymbol])
        for k,v in gd.items():
            print 'grad',k,'...'
            print v

    def only(self,group):
        self.assertEqual(len(group), 1)
        return group[0]

    def checkDicts(self,actual, expected):
        print 'actual:  ',actual
        if expected:
            print 'expected:',expected
            self.assertEqual(len(actual.keys()), len(expected.keys()))
            for k in actual.keys():
                self.assertEqual(actual[k], expected[k])

class TestProPPR(unittest.TestCase):

    def setUp(self):
        self.prog = tensorlog.ProPPRProgram.load(["test/textcat.ppr","test/textcattoy.cfacts"])
        self.prog.setWeights(self.prog.db.ones())
        self.xsyms,self.X,self.Y = self.loadExamples("test/textcattoy-train.examples",self.prog.db)
        self.numExamples = self.X.get_shape()[0] 
        self.numFeatures = self.X.get_shape()[1] 
        self.mode = tensorlog.ModeDeclaration('predict(i,o)')
        self.numWords = {'dh':4.0, 'ft':5.0, 'rw':3.0, 'sc':5.0, 'bk':5.0, 'rb':4.0, 'mv':8.0, 'hs':9.0, 'ji':6.0, 'tf':8.0, 'jm':8.0 }
    
    def testNativeRow(self):
        for i in range(self.numExamples):
            ops.TRACE = False
            pred = self.prog.eval(self.mode,[self.X.getrow(i)])[0]
            d = self.prog.db.rowAsSymbolDict(pred)
            gradDict = self.prog.evalGrad(self.mode,[self.X.getrow(i)])
#            if i<4: 
#                print 'native row',i,self.xsyms[i],d
#                print 'grad w_Pos vs w_Neg',gradDict[ops.Partial('w_Pos',('weighted',1))].sum()/gradDict[ops.Partial('w_Pos',('weighted',1))].sum()
            self.checkClass(d,self.xsyms[i],'pos',self.numWords)
            self.checkClass(d,self.xsyms[i],'neg',self.numWords)

    def testNativeMatrix(self):
        ops.TRACE = False
        pred = self.prog.eval(self.mode,[self.X])[0]
        d0 = self.prog.db.matrixAsSymbolDict(pred)
        for i,d in d0.items():
            if i<4: print 'native matrix',i,self.xsyms[i],d
            self.checkClass(d,self.xsyms[i],'pos',self.numWords)
            self.checkClass(d,self.xsyms[i],'neg',self.numWords)

    def checkClass(self,d,sym,lab,expected):
        self.assertEqual(d[lab], expected[sym])

    def loadExamples(self,filename,db):
        xsyms = []
        xs = []
        ys = []
        for line in open(filename):
            sx,sy = line.strip().split("\t")
            xsyms.append(sx)
            xs.append(db.onehot(sx))
            ys.append(db.onehot(sy))
        return xsyms,scipy.sparse.vstack(xs),scipy.sparse.vstack(ys)

if __name__=="__main__":
    if len(sys.argv)==1:
        unittest.main()

