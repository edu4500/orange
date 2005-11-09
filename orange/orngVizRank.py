import orange, sys
import OWVisAttrSelection, orngTest
import OWVisFuncts
from math import sqrt
import os, orange, orngTest
from math import sqrt
import Numeric, time
from copy import copy


# quality measure
CLASS_ACCURACY = 0
AVERAGE_CORRECT = 1
BRIER_SCORE = 2
ENTROPY_BASED = 3

# testing method
LEAVE_ONE_OUT = 0
TEN_FOLD_CROSS_VALIDATION = 1
TEST_ON_LEARNING_SET = 2

# results in the list
ACCURACY = 0 
OTHER_RESULTS = 1
LEN_TABLE = 2
ATTR_LIST = 3
TRY_INDEX = 4
REVERSE_LIST = 5

OTHER_ACCURACY = 0
OTHER_PREDICTIONS = 1
OTHER_DISTRIBUTION = 2

# evaluation algorithm
ALGORITHM_KNN = 0
ALGORITHM_FISHER = 1
ALGORITHM_HEURISTIC = 2

NUMBER_OF_INTERVALS = 6  # number of intervals to use when discretizing. used when using the very fast heuristic

# attrCont
CONT_MEAS_NONE = 0
CONT_MEAS_RELIEFF = 1
CONT_MEAS_S2N = 2
CONT_MEAS_S2NMIX = 3

# attrDisc
DISC_MEAS_NONE = 0
DISC_MEAS_RELIEFF = 1
DISC_MEAS_GAIN = 2
DISC_MEAS_GINI = 3

contMeasures = [("None", None), ("ReliefF", orange.MeasureAttribute_relief(k=10, m=50)), ("Fisher discriminant", OWVisAttrSelection.MeasureFisherDiscriminant()), ("Signal to Noise Ratio", OWVisAttrSelection.S2NMeasure()), ("Signal to Noise OVA", OWVisAttrSelection.S2NMeasureMix())]
discMeasures = [("None", None), ("ReliefF", orange.MeasureAttribute_relief(k=10, m=50)), ("Gain ratio", orange.MeasureAttribute_gainRatio()), ("Gini index", orange.MeasureAttribute_gini())]


# array of testing methods. used by calling python's apply method depending on the value of self.testingMethod
testingMethods = [orngTest.leaveOneOut, orngTest.crossValidation, orngTest.learnAndTestOnLearnData]

# visualization methods
SCATTERPLOT = 0
RADVIZ = 1

# optimization type
EXACT_NUMBER_OF_ATTRS = 0
MAXIMUM_NUMBER_OF_ATTRS = 1

class VizRank:
    
    def __init__(self, visualizationMethod = SCATTERPLOT, graph = None):
        if not graph:
            if visualizationMethod == SCATTERPLOT:
                import orngScaleScatterPlotData
                graph = orngScaleScatterPlotData.orngScaleScatterPlotData()
            elif visualizationMethod == RADVIZ:
                import orngScaleRadvizData
                graph = orngScaleRadvizData.orngScaleRadvizData()
        self.graph = graph
        self.visualizationMethod = visualizationMethod
        
        self.kValue = 10
        self.percentDataUsed = 100
        self.qualityMeasure = AVERAGE_CORRECT
        self.testingMethod = TEN_FOLD_CROSS_VALIDATION
        self.optimizationType = MAXIMUM_NUMBER_OF_ATTRS
        self.attributeCount = 4
        self.canUseMoreArguments = 0
        self.moreArgumentsCount = 4
        self.evaluationAlgorithm = ALGORITHM_KNN
        self.attrCont = CONT_MEAS_RELIEFF
        self.attrDisc = DISC_MEAS_RELIEFF
        self.data = None
        self.arguments = []                                 # a list of arguments
        self.evaluationTime = 2                             # how many minutes do we want to try to find top projections
        self.optimizeBestProjection = 0                     # do we want to try to locally improve the best projections
        self.optimizeBestProjectionTime = 2                 # how many minutes do we want to try to locally optimize the best projections
        self.useHeuristicToFindAttributeOrders = 0          # try all different placements of a group of attributes or not
        self.externalLearner = None                         # do we use knn or some external learner
        self.selectedClasses = []                           # which classes are we trying to separate
        self.learnerName = "VizRank Learner"
        self.onlyOnePerSubset = 1                           # save only the best placement of attributes in radviz
        self.maxResultListLen = 100000                      # number of projections to store in a list

        self.argumentCount = 1              # number of arguments used when classifying 
        self.argumentValueFormula = 1       # how to compute argument value

        self.locOptMaxAttrsInProj = 20      # maximum number of attributes in projection
        self.locOptProjCount = 20           # consider this number of best ranked projections
        self.attributeNameIndex = {}        # dict with indices to attributes
        
        self.allResults = []
        self.datasetName = ""
        
        # 0 - set to sqrt(N)
        # 1 - set to N / c
        self.kValueFormula = 1
        self.autoSetTheKValue = 1       # automatically set the value k


    def clearResults(self):
        self.allResults = []

    def clearArguments(self):
        self.arguments = []

    def removeTooSimilarProjections(self):
        i=0
        while i < len(self.allResults):
            if self.existsABetterSimilarProjection(i):  self.allResults.pop(i)
            else:                                       i += 1

    # test if one of the projections in self.allResults[0:index] are similar to the self.allResults[index] projection
    def existsABetterSimilarProjection(self, index):
        testAttrs = self.allResults[index][ATTR_LIST]
        for i in range(index):
            attrs = self.allResults[i][ATTR_LIST]
            if len(attrs) != len(testAttrs): continue
            diffArr = [testAttrs[j] != attrs[j] for j in range(len(attrs))]
            if sum(diffArr) < int((len(attrs)+4) * 0.20): return 1
        return 0


    def createkNNLearner(self):
        kValue = self.kValue
        if self.percentDataUsed != 100: kValue = int(kValue * self.percentDataUsed / 100.0)
        return orange.kNNLearner(k = kValue, rankWeight = 0, distanceConstructor = orange.ExamplesDistanceConstructor_Euclidean(normalize=0))
        

    def setData(self, data):
        self.data = data

        self.clearResults()
        self.clearArguments()
        
        self.selectedClasses = []
        if self.data and self.data.domain.classVar and self.data.domain.classVar.varType == orange.VarTypes.Discrete:
            self.selectedClasses = range(len(self.data.domain.classVar.values))

        if not data: return

        if self.autoSetTheKValue:
            if self.kValueFormula == 0:     self.kValue = int(sqrt(len(data)))                                 # k = sqrt(N)
            elif self.kValueFormula == 1:   self.kValue = int(len(data) / len(data.domain.classVar.values))    # k = N / c (c = # of class values)

        self.attributeNameIndex = dict([(data.domain[i].name, i) for i in range(len(data.domain))])


    def getEvaluatedAttributes(self):
        return OWVisAttrSelection.evaluateAttributes(self.data, contMeasures[self.attrCont][1], discMeasures[self.attrDisc][1])

    # return a function that is appropriate to find the best projection in a list in respect to the selected quality measure
    def getMaxFunct(self):
        if self.data.domain.classVar.varType == orange.VarTypes.Discrete and self.qualityMeasure != BRIER_SCORE: return max
        else: return min

    def addResult(self, accuracy, other_results, lenTable, attrList, tryIndex, attrReverseList = []):
        funct = self.qualityMeasure != BRIER_SCORE and max or min
        self.insertItem(accuracy, other_results, lenTable, attrList, self.findTargetIndex(accuracy, funct), tryIndex, attrReverseList)

    # use bisection to find correct index
    def findTargetIndex(self, accuracy, funct):
        top = 0; bottom = len(self.allResults)

        while (bottom-top) > 1:
            mid  = (bottom + top)/2
            if funct(accuracy, self.allResults[mid][ACCURACY]) == accuracy: bottom = mid
            else: top = mid

        if len(self.allResults) == 0: return 0
        if funct(accuracy, self.allResults[top][ACCURACY]) == accuracy:
            return top
        else: 
            return bottom

    # insert new result - give parameters: accuracy of projection, number of examples in projection and list of attributes.
    # parameter attrReverseList can be a list used by polyviz
    def insertItem(self, accuracy, other_results, lenTable, attrList, index, tryIndex, attrReverseList = None):
        if index < self.maxResultListLen:
            self.allResults.insert(index, (accuracy, other_results, lenTable, attrList, tryIndex, attrReverseList))

    # kNNEvaluate - evaluate class separation in the given projection using a heuristic or k-NN method
    def kNNComputeAccuracy(self, table):
        # select a subset of the data if necessary
        if self.percentDataUsed != 100:
            indices = orange.MakeRandomIndices2(table, 1.0-float(self.percentDataUsed)/100.0)
            testTable = table.select(indices)
        else:
            testTable = table

        if len(testTable) == 0: return 0,0

        if self.evaluationAlgorithm == ALGORITHM_KNN or self.externalLearner:
            if self.externalLearner: learner = self.externalLearner
            else:                    learner = self.createkNNLearner()
            
            results = apply(testingMethods[self.testingMethod], [[learner], testTable])
            
            # compute classification success using selected measure
            if testTable.domain.classVar.varType == orange.VarTypes.Discrete:
                currentClassDistribution = [int(v) for v in orange.Distribution(testTable.domain.classVar, testTable)]
                prediction = [0.0 for i in range(len(testTable.domain.classVar.values))]
        
                if self.qualityMeasure == AVERAGE_CORRECT:
                    for res in results.results:
                        prediction[res.actualClass] += res.probabilities[0][res.actualClass]
                    prediction = [val*100.0 for val in prediction]

                elif self.qualityMeasure == BRIER_SCORE:
                    #return orngStat.BrierScore(results)[0], results
                    for res in results.results:
                        val = 0
                        for prob in res.probabilities: val += prob*prob
                        val = val - 2*res.probabilities[res.actualClass] + 1
                        prediction[res.actualClass] += val
                    
                elif self.qualityMeasure == CLASS_ACCURACY:
                    #return 100*orngStat.CA(results)[0], results
                    for res in results.results:
                        prediction[res.actualClass] += res.classes[0]==res.actualClass
                    prediction = [val*100.0 for val in prediction]
                    
                elif self.qualityMeasure == ENTROPY_BASED:
                    # compute n/N * sum_i n_i/n * N_i/n_i * P_r_i = n/N * sum_i N_i/n * P_r_i
                    pass

                # compute accuracy only for classes that are selected as interesting. other class values do not participate in projection evaluation
                acc = sum(prediction) / float(len(testTable))
                val = sum([prediction[index] for index in self.selectedClasses])
                s = sum([currentClassDistribution[index] for index in self.selectedClasses])

                prediction = [prediction[i] / float(max(1, currentClassDistribution[i])) for i in range(len(prediction))] # turn to probabilities

                return val/float(s), (acc, prediction, list(currentClassDistribution))
                
            # for continuous class we can't compute brier score and classification accuracy
            else:
                val = 0.0
                if not results.results or not results.results[0].probabilities[0]: return 0,0
                for res in results.results:  val += res.probabilities[0].density(res.actualClass)
                val/= float(len(results.results))
                return 100.0*val, (100.0*val)

        # ###############################
        # do we want to use very fast heuristic
        # ###############################
        elif self.evaluationAlgorithm == ALGORITHM_HEURISTIC:
            # if input attributes are continuous (may be discrete for evaluating scatterplots, where we dicretize the whole domain...)
            if testTable.domain[0].varType == orange.VarTypes.Continuous and testTable.domain[1].varType == orange.VarTypes.Continuous:
                discX = orange.EquiDistDiscretization(testTable.domain[0], testTable, numberOfIntervals = NUMBER_OF_INTERVALS)
                discY = orange.EquiDistDiscretization(testTable.domain[0], testTable, numberOfIntervals = NUMBER_OF_INTERVALS)
                testTable = testTable.select([discX, discY, testTable.domain.classVar])

            currentClassDistribution = [int(v) for v in orange.Distribution(testTable.domain.classVar, testTable)]
            prediction = [0.0 for i in range(len(testTable.domain.classVar.values))]

            # create a new attribute that is a cartesian product of the two visualized attributes
            nattr = orange.EnumVariable(values=['i' for i in range(NUMBER_OF_INTERVALS*NUMBER_OF_INTERVALS)])
            nattr.getValueFrom = orange.ClassifierByLookupTable2(nattr, testTable.domain[0], testTable.domain[1])
            for i in range(NUMBER_OF_INTERVALS*NUMBER_OF_INTERVALS): nattr.getValueFrom.lookupTable[i] = i
            
            for dist in orange.ContingencyAttrClass(nattr, testTable):
                dist = list(dist)
                if sum(dist) == 0: continue
                m = max(dist)
                prediction[dist.index(m)] += m * m / float(sum(dist))

            prediction = [val*100.0 for val in prediction]             # turn prediction array into percents
            acc = sum(prediction) / float(len(testTable))               # compute accuracy for all classes
            val = 0.0; s = 0.0
            for index in self.selectedClasses:                          # compute accuracy for selected classes
                val += prediction[index]; s += currentClassDistribution[index]
            for i in range(len(prediction)): prediction[i] /= float(currentClassDistribution[i])    # turn to probabilities
            return val/float(s), (acc, prediction, currentClassDistribution)


        elif self.evaluationAlgorithm == ALGORITHM_FISHER:
            val = OWVisTools.computeFisherQuality(testTable)
            return val, None
        

    # Argumentation functions
    def findArguments(self, example):
        self.cancelArgumentation = 0
        self.clearArguments()
        self.arguments = [[] for i in range(len(self.data.domain.classVar.values))]
        argumentList = []
                
        if len(self.allResults) == 0:
            print 'VizRank Argumentation: To find arguments you first have to evaluate some projections by clicking "Start evaluating projections" in the Main tab.'
            return (None,None)

        testExample = ["?"] * len(example.domain.attributes)
        
        foundArguments = 0
        for index in range(min(len(self.allResults), self.argumentCount+300)):       # use only best argumentCount projections for argumentation
            (accuracy, other_results, lenTable, attrList, tryIndex, attrReverseList) = self.allResults[index]
            
            validExample = 1
            for attr in attrList:
                if example[attr].isSpecial():
                    validExample = 0
                    continue

            if not validExample:
                self.printVerbose("Warning: orngVizRank.py:findArguments: Tested example has a missing value at one of the visualized attributes. Skipping the projection.")
                continue

            attrVals = []
            for i in range(len(attrList)):
                attrIndex = self.graph.attributeNameIndex[attrList[i]]
                if testExample[attrIndex] == "?":
                    testExample[attrIndex] = self.graph.scaleExampleValue(example, attrIndex)
                attrVals.append(testExample[attrIndex])
                        
            [xTest, yTest] = self.graph.getProjectedPointPosition(attrList, attrVals)
            table = self.graph.createProjectionAsExampleTable([self.attributeNameIndex[attr] for attr in attrList])
            learner = self.externalLearner or self.createkNNLearner()
            classifier = learner(table)
            (classValue, prob) = classifier(orange.Example(table.domain, [xTest, yTest, "?"]), orange.GetBoth)
            classValue = int(classValue)
            if self.argumentValueFormula == 0:
                value = accuracy
                if index >= self.argumentCount-1: self.cancelArgumentation = 1   # we stop searching for arguments if argumentValueFormula = 0 and we already considered enough top projections
            elif self.argumentValueFormula == 1:
                value = 0.5 * accuracy + 50.0 * prob[classValue]
            else:
                value = 100.0 * prob[classValue]

            ind = self.getArgumentIndex(value, classValue)
            self.arguments[classValue].insert(ind, (None, value, accuracy, 100.0 * prob[classValue], prob, attrList, index))
            argumentList.append((value, classValue))
            

        if len(argumentList) == 0: return (None, None)

        # sort all arguments and compute the outcome
        argumentList.sort()
        argumentList.reverse()
        vals = [0.0 for i in range(len(self.arguments))]
        for i in range(min(self.argumentCount, len(argumentList))):
            vals[argumentList[i][1]] += argumentList[i][0]

        if self.canUseMoreArguments and (max(vals)*100.0 / sum(vals) < self.moreArgumentsCount):
            for i in range(self.argumentCount, len(argumentList)):
                if max(vals)*100.0 / sum(vals) > self.moreArgumentsCount: break
                vals[argumentList[i][1]] += argumentList[i][0]

        suma = sum(vals)
        dist = orange.DiscDistribution([val/float(suma) for val in vals]);  dist.variable = self.data.domain.classVar
        classValue = example.domain.classVar[vals.index(max(vals))]
        return classValue, dist


    def getArgumentIndex(self, value, classValue):
        top = 0; bottom = len(self.arguments[classValue])
        while (bottom-top) > 1:
            mid  = (bottom + top)/2
            if max(value, self.arguments[classValue][mid][1]) == value: bottom = mid
            else: top = mid

        if len(self.arguments[classValue]) == 0: return 0
        if max(value, self.arguments[classValue][top][1]) == value:  return top
        else:                                                        return bottom

    def isOptimizationCanceled(self):
        return (time.time() - self.startTime) / 60 >= self.optimizeBestProjectionTime

    def isEvaluationCanceled(self):
        return (time.time() - self.startTime) / 60 >= self.evaluationTime

    def evaluateProjections(self):
        evaluatedProjections = 0
        self.startTime = time.time()

        maxFunct = self.getMaxFunct()
        self.clearResults()
        self.clearArguments()
        if self.__class__ != VizRank:
            self.disableControls()
            self.parentWidget.progressBarInit()
            from qt import qApp
        
        if self.visualizationMethod == SCATTERPLOT:
            evaluatedAttributes = OWVisAttrSelection.evaluateAttributes(self.data, contMeasures[self.attrCont][1], discMeasures[self.attrDisc][1])
            contVars = [orange.FloatVariable(attr.name) for attr in self.data.domain.attributes]
            contDomain = orange.Domain(contVars + [self.data.domain.classVar])
            fullData = orange.ExampleTable(contDomain)
            attrCount = len(self.data.domain.attributes)
            for i in range(len(self.data)):
                fullData.append([self.graph.noJitteringScaledData[ind][i] for ind in range(attrCount)] + [self.data[i].getclass()])

            # if we want to use heuristics, we first discretize all attributes - this way we discretize the attributes only once
            if self.evaluationAlgorithm == ALGORITHM_HEURISTIC:
                attrs = [orange.EquiDistDiscretization(fullData.domain[attr], fullData, numberOfIntervals = NUMBER_OF_INTERVALS) for attr in fullData.domain.attributes]
                for attr in attrs: attr.name = attr.name[2:]    # remove the "D_" in front of the attribute name
                fullData = fullData.select(attrs + [fullData.domain.classVar])
            
            count = len(evaluatedAttributes)*(len(evaluatedAttributes)-1)/2
            strCount = OWVisFuncts.createStringFromNumber(count)
            
            for i in range(len(evaluatedAttributes)):
                for j in range(i):
                    attr1 = self.attributeNameIndex[evaluatedAttributes[j]]; attr2 = self.attributeNameIndex[evaluatedAttributes[i]]
                    evaluatedProjections += 1
                    if self.isEvaluationCanceled():
                        self.finishEvaluation(evaluatedProjections)
                        return
                    
                    valid = self.graph.validDataArray[attr1] + self.graph.validDataArray[attr2] - 1
                    table = fullData.select([attr1, attr2, self.data.domain.classVar.name])
                    table = table.select(list(valid))
                    
                    accuracy, other_results = self.kNNComputeAccuracy(table)
                    self.addResult(accuracy, other_results, len(table), [self.data.domain[attr1].name, self.data.domain[attr2].name], evaluatedProjections)
                    
                    if self.__class__ != VizRank:
                        self.setStatusBarText("Evaluated %s/%s projections..." % (OWVisFuncts.createStringFromNumber(evaluatedProjections), strCount))
                        self.parentWidget.progressBarSet(100.0*evaluatedProjections/float(count))

        # #################### RADVIZ ################################
        elif self.visualizationMethod == RADVIZ:
            import orngScaleRadvizData
            # replace attribute names with indices in domain - faster searching
            classIndex = self.attributeNameIndex[self.data.domain.classVar.name]

            # variables and domain for the table
            domain = orange.Domain([orange.FloatVariable("xVar"), orange.FloatVariable("yVar"), self.data.domain.classVar])
            minLength = (self.optimizationType == EXACT_NUMBER_OF_ATTRS and self.attributeCount) or 3
            maxLength = self.attributeCount
            anchorList = [(self.graph.createXAnchors(i), self.graph.createYAnchors(i)) for i in range(minLength, maxLength+1)]
            classListFull = Numeric.transpose(self.data.toNumeric("c")[0])[0]
                
            # ################### WITH HEURISTIC ##########################
            if self.useHeuristicToFindAttributeOrders:
                attributes, attrsByClass = OWVisAttrSelection.findAttributeGroupsForRadviz(self.data, OWVisAttrSelection.S2NMeasureMix())
                attributes = [self.attributeNameIndex[name] for name in attributes]
                attrsByClass = [[self.attributeNameIndex[name] for name in arr] for arr in attrsByClass]
                numClasses = len(self.data.domain.classVar.values)

                for z in range(minLength-1, len(attributes)):
                    for u in range(minLength-1, maxLength):
                        projs = OWVisFuncts.createProjections(numClasses, u+1)
                        
                        combinations = OWVisFuncts.combinations(range(z), u)

                        XAnchors = anchorList[u+1-minLength][0]
                        YAnchors = anchorList[u+1-minLength][1]
                        
                        for comb in combinations:
                            comb += [z]  # remove the value of this attribute subset
                            counts = [0 for i in range(numClasses)]
                            for v in comb: counts[v%numClasses] += 1
                            if min(counts) < (u+1) / numClasses: continue   # ignore combinations that don't have good attributes for all class values

                            attrList = [[] for i in range(numClasses)]
                            for v in comb: attrList[v%numClasses].append(attributes[v])

                            attrs = [attributes[c] for c in comb]

                            validData = self.graph.getValidList(attrs)
                            classList = Numeric.compress(validData, classListFull)
                            selectedData = Numeric.compress(validData, Numeric.take(self.graph.noJitteringScaledData, attrs))
                            sum_i = self.graph._getSum_i(selectedData)

                            tempList = []

                            # for every permutation compute how good it separates different classes
                            for proj in projs:
                                if self.isEvaluationCanceled():
                                    self.finishEvaluation(evaluatedProjections)
                                    return
                                
                                try:
                                    permutation = [attrList[i][j] for (i,j) in proj]
                                    table = self.graph.createProjectionAsExampleTable(permutation, validData, classList, sum_i, XAnchors, YAnchors, domain)
                                    accuracy, other_results = self.kNNComputeAccuracy(table)
                                    
                                    # save the permutation
                                    if not self.onlyOnePerSubset:
                                        self.addResult(accuracy, other_results, len(table), [self.graph.attributeNames[i] for i in permutation], evaluatedProjections)
                                    else:
                                        tempList.append((accuracy, other_results, len(table), [self.graph.attributeNames[i] for i in permutation]))

                                    evaluatedProjections += 1
                                    if self.__class__ != VizRank:
                                        self.setStatusBarText("Evaluated %s projections (%d attributes)..." % (OWVisFuncts.createStringFromNumber(evaluatedProjections), z+1))
                                        qApp.processEvents()        # allow processing of other events
                                except:
                                    pass

                            if self.onlyOnePerSubset and len(tempList) > 0:   # return only the best attribute placements
                                (acc, other_results, lenTable, attrList) = maxFunct(tempList)
                                self.addResult(acc, other_results, lenTable, attrList, evaluatedProjections)

                        

            # ################### WITHOUT HEURISTIC ##########################
            else:
                evaluatedAttributes = OWVisAttrSelection.evaluateAttributes(self.data, contMeasures[self.attrCont][1], discMeasures[self.attrDisc][1])
                attributes = [self.attributeNameIndex[name] for name in evaluatedAttributes]
                self.totalPossibilities = 0
                for i in range(minLength, maxLength+1): self.totalPossibilities += OWVisFuncts.combinationsCount(i, len(attributes)) * OWVisFuncts.fact(i-1)/2
            
                #if self.totalPossibilities > 200000: self.printVerbose("OWRadviz: Warning: There are %s possible radviz projections with this set of attributes"% (OWVisFuncts.createStringFromNumber(self.graph.totalPossibilities)))

                # build list of indices for permutations of different number of attributes
                permutationIndices = {}
                for i in range(minLength, maxLength+1):
                    indices = {}
                    orngScaleRadvizData.buildPermutationIndexList(range(0, i), [], indices)
                    permutationIndices[i] = indices

                for z in range(minLength-1, len(attributes)):
                    for u in range(minLength-1, maxLength):
                        combinations = OWVisFuncts.combinations(attributes[:z], u)

                        XAnchors = anchorList[u+1-minLength][0]
                        YAnchors = anchorList[u+1-minLength][1]
                        
                        for attrList in combinations:
                            attrs = attrList + [attributes[z]] # remove the value of this attribute subset
                            permIndices = permutationIndices[len(attrs)]
                            
                            validData = self.graph.getValidList(attrs)
                            classList = Numeric.compress(validData, classListFull)
                            selectedData = Numeric.compress(validData, Numeric.take(self.graph.noJitteringScaledData, attrs))
                            sum_i = self.graph._getSum_i(selectedData)
                            tempList = []

                            # for every permutation compute how good it separates different classes            
                            for ind in permIndices.values():
                                permutation = [attrs[val] for val in ind]
                                if self.isEvaluationCanceled():
                                    self.finishEvaluation(evaluatedProjections)
                                    return

                                table = self.graph.createProjectionAsExampleTable(permutation, validData, classList, sum_i, XAnchors, YAnchors, domain)
                                accuracy, other_results = self.kNNComputeAccuracy(table)
                                
                                # save the permutation
                                if self.onlyOnePerSubset:
                                    tempList.append((accuracy, other_results, len(table), [self.graph.attributeNames[i] for i in permutation]))
                                else:
                                    self.addResult(accuracy, other_results, len(table), [self.graph.attributeNames[i] for i in permutation], evaluatedProjections)
                                    
                                evaluatedProjections += 1
                                if self.__class__ != VizRank: qApp.processEvents()        # allow processing of other events
                                    
                            if self.__class__ != VizRank:
                                self.parentWidget.progressBarSet(100.0*evaluatedProjections/float(self.totalPossibilities))
                                self.setStatusBarText("Evaluated %s projections..." % (OWVisFuncts.createStringFromNumber(evaluatedProjections)))

                            if self.onlyOnePerSubset:   # return only the best attribute placements
                                (acc, other_results, lenTable, attrList) = maxFunct(tempList)
                                self.addResult(acc, other_results, lenTable, attrList, evaluatedProjections)

        self.finishEvaluation(evaluatedProjections)
                        

    def finishEvaluation(self, evaluatedProjections):
        if self.__class__ != VizRank:
            secs = time.time() - self.startTime
            self.setStatusBarText("Finished evaluation (evaluated %d projections in %d min, %d sec)" % (evaluatedProjections, secs/60, secs%60))
            self.parentWidget.progressBarFinished()
            self.enableControls()
            self.finishedAddingResults()
            if self.parentWidget: self.parentWidget.showSelectedAttributes()
            

    def getProjectionQuality(self, attrList, useAnchorData = 0):
        if not self.data: return 0.0, None

        attrIndices = [self.attributeNameIndex[attr] for attr in attrList]

        if self.visualizationMethod == SCATTERPLOT:
            table = self.graph.createProjectionAsExampleTable(attrIndices)
        elif self.visualizationMethod == RADVIZ:
            table = self.graph.createProjectionAsExampleTable(attrIndices, useAnchorData = useAnchorData)
        return self.kNNComputeAccuracy(table)


    def optimizeBestProjections(self, bestFeatureSubsetSize = 200, restartWhenImproved = 1):
        count = min(len(self.allResults), self.locOptProjCount)
        attrLists = [self.allResults[i][ATTR_LIST] for i in range(count)]                                   # create a list of attributes that are in the top projections
        attrLists = [[self.attributeNameIndex[name] for name in projection] for projection in attrLists]    # find indices from the attribute names
        accuracys = [self.getProjectionQuality(self.allResults[i][ATTR_LIST])[0] for i in range(count)]
        domain = orange.Domain([orange.FloatVariable("xVar"), orange.FloatVariable("yVar"), self.data.domain.classVar])
        attributes = [self.attributeNameIndex[name] for name in OWVisAttrSelection.evaluateAttributes(self.data, contMeasures[self.attrCont][1], discMeasures[self.attrDisc][1])[:bestFeatureSubsetSize]]
        self.startTime = time.time()
        evaluatedProjections = 0
        lenOfAttributes = len(attributes)
        maxFunct = self.getMaxFunct()

        if self.__class__ != VizRank:
            self.disableControls()
            from qt import qApp
        
        if self.visualizationMethod == SCATTERPLOT:
            classIndex = self.attributeNameIndex[self.data.domain.classVar.name]
            classListFull = Numeric.transpose(self.data.toNumeric("c")[0])[0]

            for i in range(len(attrLists)):
                projection = attrLists[i]
                accuracy = accuracys[i]
                optimizedProjection = 1
                
                while optimizedProjection:
                    significantImprovement = 0
                    
                    strTotalAtts = OWVisFuncts.createStringFromNumber(lenOfAttributes)
                    listOfCanditates = []
                    for (attrIndex, attr) in enumerate(attributes):
                        if attr in projection: continue
                        if significantImprovement and restartWhenImproved: break        # if we found a projection that is significantly better than the currently best projection then restart the search with this projection

                        projections = [[projection[0], attr], [attr, projection[1]]]
                        
                        tempList = []
                        for testProj in projections:
                            table = self.graph.createProjectionAsExampleTable(testProj, domain = domain)
                            acc, other_results = self.kNNComputeAccuracy(table)
                            
                            tempList.append((acc, other_results, len(table), testProj))  # save the permutation

                            evaluatedProjections += 1
                            if self.__class__ != VizRank: qApp.processEvents()        # allow processing of other events
                            if self.isOptimizationCanceled():
                                self.finishEvaluation(evaluatedProjections)
                                return

                        # return only the best attribute placements
                        (acc, other_results, lenTable, attrList) = maxFunct(tempList)
                        if maxFunct(acc, accuracy) == acc:
                            listOfCanditates.append((acc, attrList))
                            self.addResult(acc, other_results, lenTable, [self.graph.attributeNames[i] for i in attrList], 0)
                            if self.__class__ != VizRank: self.setStatusBarText("Found a better projection with accuracy: %2.2f%%" % (acc))
                            if max(acc, accuracy)/min(acc, accuracy) > 1.0001: optimizedProjection = 1
                            if max(acc, accuracy)/min(acc, accuracy) > 1.005:  significantImprovement = 1
                        else:
                            if self.__class__ != VizRank:                      self.setStatusBarText("Evaluated %s projections (attribute %s/%s). Last accuracy was: %2.2f%%" % (OWVisFuncts.createStringFromNumber(evaluatedProjections), OWVisFuncts.createStringFromNumber(attrIndex), strTotalAtts, acc))
                            # if the found projection is at least 98% as good as the one optimized, add it to the list of projections anyway
                            if min(acc, accuracy)/max(acc, accuracy) > 0.98:   self.addResult(acc, other_results, lenTable, [self.graph.attributeNames[i] for i in attrList], 1)

                    # select the best new projection and say this is now our new projection to optimize    
                    if len(listOfCanditates) > 0:
                        (accuracy, projection) = maxFunct(listOfCanditates)
                        if self.__class__ != VizRank:
                            self.setStatusBarText("Increased accuracy to %2.2f%%" % (accuracy))

        elif self.visualizationMethod == RADVIZ:
            import orngScaleRadvizData
            numClasses = len(self.data.domain.classVar.values)
            anchorList = [(self.graph.createXAnchors(i), self.graph.createYAnchors(i)) for i in range(3, self.locOptMaxAttrsInProj+1)]
            classListFull = Numeric.transpose(self.data.toNumeric("c")[0])[0]

            for i in range(len(attrLists)):
                projection = attrLists[i]
                accuracy = accuracys[i]
                optimizedProjection = 1
                
                while optimizedProjection:
                    optimizedProjection = 0
                    significantImprovement = 0
                    
                    # in the first step try to find a better projection by substituting an existent attribute with a new one
                    # in the second step try to find a better projection by adding a new attribute to the circle
                    for iteration in range(2):
                        if (len(projection) + iteration > self.locOptMaxAttrsInProj): continue    
                        if iteration == 1 and optimizedProjection: continue             # if we already found a better projection with replacing an attribute then don't try to add a new atribute
                        strTotalAtts = OWVisFuncts.createStringFromNumber(lenOfAttributes)
                        listOfCanditates = []
                        for (attrIndex, attr) in enumerate(attributes):
                            if attr in projection: continue
                            if significantImprovement and restartWhenImproved: break        # if we found a projection that is significantly better than the currently best projection then restart the search with this projection

                            projections = [copy(projection) for i in range(len(projection))]
                            if iteration == 0:  # replace one attribute in each projection with attribute attr
                                count = len(projection)
                                for i in range(count): projections[i][i] = attr
                            elif iteration == 1:
                                count = len(projection) + 1
                                for i in range(count-1): projections[i].insert(i, attr)

                            if len(anchorList) <= count-3: anchorList.append((self.createXAnchors(count), self.createYAnchors(count)))

                            XAnchors = anchorList[count-3][0]
                            YAnchors = anchorList[count-3][1]
                            validData = self.graph.getValidList(projections[0])
                            classList = Numeric.compress(validData, classListFull)
                            
                            tempList = []
                            for testProj in projections:
                                table = self.graph.createProjectionAsExampleTable(testProj, validData, classList, None, XAnchors, YAnchors, domain)
                                acc, other_results = self.kNNComputeAccuracy(table)
                                tempList.append((acc, other_results, len(table), testProj))

                                evaluatedProjections += 1
                                if self.__class__ != VizRank: qApp.processEvents()        # allow processing of other events
                                if self.isOptimizationCanceled():
                                    self.finishEvaluation(evaluatedProjections)
                                    return

                            # return only the best attribute placements
                            (acc, other_results, lenTable, attrList) = maxFunct(tempList)
                            if maxFunct(acc, accuracy) == acc:
                                listOfCanditates.append((acc, attrList))
                                self.addResult(acc, other_results, lenTable, [self.graph.attributeNames[i] for i in attrList], 0)
                                if self.__class__ != VizRank: self.setStatusBarText("Found a better projection with accuracy: %2.2f%%" % (acc))
                                if max(acc, accuracy)/min(acc, accuracy) > 1.001:  optimizedProjection = 1
                                if max(acc, accuracy)/min(acc, accuracy) > 1.005:  significantImprovement = 1
                            else:
                                if self.__class__ != VizRank:                     self.setStatusBarText("Evaluated %s projections (attribute %s/%s). Last accuracy was: %2.2f%%" % (OWVisFuncts.createStringFromNumber(evaluatedProjections), OWVisFuncts.createStringFromNumber(attrIndex), strTotalAtts, acc))
                                # if the found projection is at least 99% as good as the one optimized, add it to the list of projections anyway
                                if min(acc, accuracy)/max(acc, accuracy) > 0.99:  self.addResult(acc, other_results, lenTable, [self.graph.attributeNames[i] for i in attrList], 1)

                        # select the best new projection and say this is now our new projection to optimize    
                        if len(listOfCanditates) > 0:
                            (accuracy, projection) = maxFunct(listOfCanditates)
                            if self.__class__ != VizRank: self.setStatusBarText("Increased accuracy to %2.2f%%" % (accuracy))

        if self.__class__ != VizRank:
            secs = time.time() - self.startTime
            self.setStatusBarText("Finished evaluation (evaluated %s projections in %d min, %d sec)" % (OWVisFuncts.createStringFromNumber(evaluatedProjections), secs/60, secs%60))
            self.parentWidget.progressBarFinished()



# ###############################################################################################################################################
# ######       VIZRANK LEARNERS, CLASSIFIERS       ##############################################################################################
# ###############################################################################################################################################

# #############################################################################
# class that represents kNN classifier that classifies examples based on top evaluated projections
class VizRankClassifier(orange.Classifier):
    def __init__(self, vizrank, data, bestFeatureSubsetSize = 200):
        self.VizRank = vizrank

        if vizrank.__class__ != VizRank:
            self.VizRank.parentWidget.cdata(data, clearResults = 1)
        else:
            self.VizRank.graph.setData(data)
            self.VizRank.setData(data)

        if self.VizRank.__class__ != VizRank: self.VizRank.useTimeLimit = 1                

        self.VizRank.evaluateProjections()
        
        # do we want to optimize current projection. if yes then spend the same amount of time to optimize it            
        if self.VizRank.optimizeBestProjection:
            self.VizRank.optimizeBestProjections(bestFeatureSubsetSize)
            self.VizRank.removeTooSimilarProjections()

        if self.VizRank.__class__ != VizRank: del self.VizRank.useTimeLimit


    # for a given example run argumentation and find out to which class it most often fall        
    def __call__(self, example, returnType):
        if self.VizRank.__class__ != VizRank:
            table = orange.ExampleTable(example.domain)
            table.append(example)
            self.VizRank.parentWidget.subsetdata(table, 0)       # show the example is we use the widget
            classVal, dist = self.VizRank.findArguments(example, 0, 0)
        else:
            classVal, dist = self.VizRank.findArguments(example)
        

        if returnType == orange.GetBoth: return classVal, dist
        else:                            return classVal
        

# #############################################################################
# learner that builds VizRankClassifier
class VizRankLearner(orange.Learner):
    def __init__(self, visualizationMethod = SCATTERPLOT, vizrank = None, graph = None):
        if not vizrank:
            vizrank = VizRank(visualizationMethod, graph)
        self.VizRank = vizrank
        self.name = self.VizRank.learnerName
        
        
    def __call__(self, examples, weightID = 0, bestFeatureSubsetSize = 200):
        return VizRankClassifier(self.VizRank, examples, bestFeatureSubsetSize)

