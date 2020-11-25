import os
import xml.etree.ElementTree as ET
import re
import json
import requests
from flask import Flask, request, jsonify, Response

app = Flask(__name__)
port = int(os.environ.get('PORT', 3000))
surveyId = "<SV_b1tGz1OB0zn9mOV>"
apiToken = '<o3xMv8hzFF2CR6CgcnWmMRJtWhC4M67MJ2CopPxU>'
dataCenter = '<fra1>'

def resetMemory(memory):
    del memory['startSurvey']
    del memory['surveySessionId']

    del memory['questions']
    del memory['numberOfQuestions']
    del memory['numberOfQuestionsAnswered']

    del memory['currentQuestionNumber']
    del memory['currentQuestionType']
    del memory['currentMessage']

    del memory['advance']
    
    return memory

def cleanhtml(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    cleantext = cleantext.replace("&nbsp;", " ")
    return cleantext

def isMCQuestion(currentQuestionDetails):
    value = False
    print(str(currentQuestionDetails))
    if currentQuestionDetails['type'] == 'mc':
        value = True
    
    return value

def isNPSQuestion(currentQuestionDetails):
    value = False
    if currentQuestionDetails['type'] == 'mc' and len(currentQuestionDetails['options']['columnLabels']) == 2 and currentQuestionDetails['display'].startswith('On a scale from'):
        value = True
        
    return value

def isTextQuestion(currentQuestionDetails):
    value = False
    if currentQuestionDetails['type'] == 'te':
        value = True
    
    return value

def isDBQuestion(currentQuestionDetails):
    value = False
    if currentQuestionDetails['type'] == 'db':
        value = True
    
    return value

def isYesNoQuestion(currentQuestionDetails):
    value = False
    if isMCQuestion(currentQuestionDetails):
        if (currentQuestionDetails['choices']) and (len(currentQuestionDetails['choices']) == 2) and (cleanhtml(currentQuestionDetails['choices'][0]['display']) == "Yes") and (cleanhtml(currentQuestionDetails['choices'][1]['display']) == "No"):
            value = True 
    
    return value

def getQuestionText(currentQuestionDetails, questionNumber):
    currentQuestionText = cleanhtml(currentQuestionDetails['display'])
    print(currentQuestionText)
    
    questionNumberText = ""
    
    if questionNumber == 0 :
        questionNumberText = "first"
        
    else : 
        questionNumberText =  "next"
        
    if isMCQuestion(currentQuestionDetails):
        if isNPSQuestion(currentQuestionDetails):
            noOfChoices = len(currentQuestionDetails['choices'])
            columnLabels = currentQuestionDetails['options']['columnLabels']
            currentQuestionOptionText = "with zero being " + columnLabels[0] + " and " + str(noOfChoices - 1) + " being " + columnLabels[1]
            currentQuestionText = currentQuestionText + " " + currentQuestionOptionText                  
        
        fullSpeakOutput = "Here is your " + questionNumberText + " question, " + currentQuestionText

    elif currentQuestionDetails['type'] == 'te' or currentQuestionDetails['type'] == 'db':
        fullSpeakOutput = currentQuestionText
    
    print(fullSpeakOutput)             
    return fullSpeakOutput

def getReplies(currentQuestionDetails, questionNumber, full_speak_output):
    if isMCQuestion(currentQuestionDetails):
        if isYesNoQuestion(currentQuestionDetails):
            replyButtons = [{
                                "title" : "Yes",
                                "value" : "yes"
                            },{
                                "title" : "No",
                                "value" : "no"
                            }]
        
        else:
            currentQuestionOptions = currentQuestionDetails['choices']
            replyButtons = []

            for index, option in enumerate(currentQuestionOptions):
                title = cleanhtml(option['display'])
                optionValue = option['choiceId']
                reply = {
                                "title" : title,
                                "value" : optionValue
                            }
                replyButtons.append(reply)

        replies =   [{
                        "type": "quickReplies",
                        "content": {
                            "title": full_speak_output,
                            "buttons":replyButtons
                        }
                    }]
            
                
    elif currentQuestionDetails['type'] == 'te' or currentQuestionDetails['type'] == 'db':
        replies = [{ 
                    'type': 'text', 
                    'content': full_speak_output, 
                }]
        
    return replies

def getResponse(memory, answer):
    surveySessionId = memory["surveySessionId"]
    questions = memory["questions"]
    currentQuestionNumber = memory["currentQuestionNumber"]

    if surveySessionId :
        baseUrl = "https://{0}.qualtrics.com/API/v3/surveys/{1}/sessions/{2}".format(dataCenter, surveyId, surveySessionId)
        headers = {
            "x-api-token": apiToken,
            "Content-Type": "application/json"
        }

        data = { 
            "responses": {}
        }

        current_question_details = questions[currentQuestionNumber]
        qId = current_question_details['questionId']


        data["responses"][qId] = answer

        if currentQuestionNumber == len(questions) - 1:
            data["advance"] = True
            memory["advance"] = True
        else :
            data["advance"] = False
            memory["advance"] = False

        response = requests.post(baseUrl, json=data, headers=headers)
        response_data = response.json()
    
        if memory["advance"] == False and response_data['result']['responses'][qId]:
            #update counter to next question
            memory["currentQuestionNumber"] = memory["currentQuestionNumber"] + 1
            memory["numberOfQuestionsAnswered"] = memory["numberOfQuestionsAnswered"] + 1
                    
            currentQuestionDetails = memory["questions"][memory["currentQuestionNumber"]]
            memory["currentQuestionType"] = {"yesno" : isYesNoQuestion(currentQuestionDetails),
                                                            "option" : isMCQuestion(currentQuestionDetails) and not(isYesNoQuestion(currentQuestionDetails)),
                                                            "te" : isTextQuestion(currentQuestionDetails),
                                                            "db" : isDBQuestion(currentQuestionDetails)
                                                            }
            
            question_speak_output = getQuestionText(currentQuestionDetails, memory["currentQuestionNumber"])
            memory["currentMessage"] = question_speak_output
            full_speak_output = "Your answer has been recorded. " + question_speak_output

            replies = getReplies(currentQuestionDetails, memory["currentQuestionNumber"], full_speak_output)
            
            return jsonify( 
                status=200, 
                replies=replies, 
                conversation={ 
                    'memory': memory
                } 
            )

        elif memory["advance"] == True and response_data['result']['done']:
            memory["numberOfQuestionsAnswered"] = memory["numberOfQuestionsAnswered"] + 1
                    
            full_speak_output = cleanhtml(response_data['result']['done']) + " Goodbye!"

            memory = resetMemory(memory)
            memory["currentMessage"] = full_speak_output

            return jsonify( 
                status=200, 
                replies=[{ 
                    'type': 'text', 
                    'content': full_speak_output, 
                }], 
                conversation={ 
                    'memory': memory
                } 
            )

        elif memory["advance"] == True and response_data['result']['done'] == False and response_data['result']['questions']:
            memory["numberOfQuestionsAnswered"] = memory["numberOfQuestionsAnswered"] + 1
                    
            memory["questions"].extend(response_data['result']['questions'])
            memory["numberOfQuestions"] = len(memory["questions"]) 
                    
            memory["currentQuestionNumber"] = memory["currentQuestionNumber"] + 1
                    
            currentQuestionDetails = memory["questions"][memory["currentQuestionNumber"]]
            memory["currentQuestionType"] = {"yesno" : isYesNoQuestion(currentQuestionDetails),
                                                            "option" : isMCQuestion(currentQuestionDetails) and not(isYesNoQuestion(currentQuestionDetails)),
                                                            "te" : isTextQuestion(currentQuestionDetails),
                                                            "db" : isDBQuestion(currentQuestionDetails)
                                                            }
                    
                    
            question_speak_output = getQuestionText(currentQuestionDetails, memory["currentQuestionNumber"])
            memory["currentMessage"] = question_speak_output
            full_speak_output = "Your answer has been recorded. " + question_speak_output

            replies = getReplies(currentQuestionDetails, memory["currentQuestionNumber"], full_speak_output)
                    
                    
            return jsonify( 
                status=200, 
                replies=replies, 
                conversation={ 
                    'memory': memory
                } 
            )

        else:
            memory = resetMemory(memory)
            return jsonify( 
                status=200, 
                replies=[{ 
                    'type': 'text', 
                    'content': "There was an issue recording your answer. Please say, start survey, to restart your survey", 
                }], 
                conversation={ 
                    'memory': memory
                } 
            )

    else: 
        memory = resetMemory(memory)
        return jsonify( 
                status=200, 
                replies=[{ 
                    'type': 'text', 
                    'content': "There is an issue with your survey session. Would you like to restart your survey?", 
                }], 
                conversation={ 
                    'memory': memory
                } 
            )



@app.route('/', methods=['GET', 'POST'])
def index():
    return "Proxy for Qualtrics APIs"

@app.route('/getsession', methods=['POST'])
def getSession():
    req = json.loads(request.get_data())
    memory = req['conversation']['memory']
    surveyIdfromMemory = memory["surveyId"]

    if surveyIdfromMemory :
        surveyId = surveyIdfromMemory

    baseUrl = "https://{0}.qualtrics.com/API/v3/surveys/{1}/sessions".format(dataCenter, surveyId)
    headers = {
        "x-api-token": apiToken,
        "Content-Type": "application/json"
    }

    data = { 
        "language": "EN"
    }
    
    response = requests.post(baseUrl, json=data, headers=headers)
        
    response_data = response.json()

    # memory = req['conversation']['memory']
    memory["surveySessionId"] = response_data['result']['sessionId']
    questions = response_data['result']['questions']
    memory["questions"] = questions
                
    memory["numberOfQuestions"] = len(questions) 
    memory["numberOfQuestionsAnswered"] = 0 
    memory["currentQuestionNumber"] = 0 
    currentQuestionDetails = memory["questions"][memory["currentQuestionNumber"]]
    memory["currentQuestionType"] = {"yesno" : isYesNoQuestion(currentQuestionDetails),
                                                "option" : isMCQuestion(currentQuestionDetails) and not(isYesNoQuestion(currentQuestionDetails)),
                                                "te" : isTextQuestion(currentQuestionDetails)
                                                }

    full_speak_output = getQuestionText(currentQuestionDetails, memory["currentQuestionNumber"])
    memory["currentMessage"] = full_speak_output
    memory["startSurvey"] = True

    replies = getReplies(currentQuestionDetails, memory["currentQuestionNumber"], full_speak_output)
    
    
    return jsonify( 
        status=200, 
        replies=replies, 
        conversation={ 
            'memory': memory
        } 
    )

@app.route('/updateSessionwithYesNoAnswer', methods=['POST'])
def updateSessionwithYesNoAnswer():
    req = json.loads(request.get_data())
    memory = req['conversation']['memory']
    yesno = memory['yesno']['choiceid']

    answer = {}
    answer[yesno] = {
                            "selected": True
                        }

    return getResponse(memory, answer)


@app.route('/updateSessionwithOptionAnswer', methods=['POST'])
def updateSessionwithOptionAnswer():

    req = json.loads(request.get_data())
    memory = req['conversation']['memory']
    optionId = memory['optionNumber']['scalar']

    answer = {}
    answer[optionId] = {
                            "selected": True
                        }

    return getResponse(memory, answer)


@app.route('/updateSessionwithTextAnswer', methods=['POST'])
def updateSessionwithTextAnswer():
    req = json.loads(request.get_data())
    memory = req['conversation']['memory']
    answer = req['nlp']['source']

    return getResponse(memory, answer)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, debug=True)
