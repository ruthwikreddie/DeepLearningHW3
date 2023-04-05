# -*- coding: utf-8 -*-
"""Untitled6.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1XR60fTItGXcdyMRH0HyxobfpwXw1TvAN
"""

!pip install jiwer
!pip install evaluate
!pip install transformers

# -*- coding: utf-8 -*-
"""Untitled5.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1jUTL-FIlAFHrCN9-AMlyNRWpiagfn1_T
"""

import requests
import json
import torch
import torch.nn as nn
import os
from tqdm import tqdm
from transformers import BertModel, BertTokenizerFast, AdamW

from torch.utils.data import Dataset, DataLoader
from torch.optim.lr_scheduler import ExponentialLR
from evaluate import load
import matplotlib.pyplot as plt
#check CUDA availability
device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')
print(device)
def get_data(path): 
    with open(path, 'r') as f:
        raw_data = json.load(f)
    return raw_data
path = '/content/spoken_train-v1.1.json' # path to the JSON file in your mounted Google Drive
data = get_data(path)

num_of_questions = 0
num_of_possible = 0
num_of_impossible = 0

def get_data(path): 
    with open(path, 'rb') as f:
        raw_data = json.load(f)
    contexts = []
    questions = []
    answers = []
    num_q = 0
    num_pos = 0
    num_imp = 0
    for group in raw_data['data']:
        for paragraph in group['paragraphs']:
            context = paragraph['context']
            for qa in paragraph['qas']:
                question       = qa['question']
                num_q  = num_q+1
                for answer in qa['answers']:
                    contexts.append(context.lower())
                    questions.append(question.lower())
                    answers.append(answer)
    return num_q, num_pos, num_imp, contexts, questions, answers

num_q, num_pos, num_imp, train_contexts, train_questions, train_answers = get_data('spoken_train-v1.1.json')
num_of_questions  = num_q
num_of_possible = num_pos
num_of_impossible  = num_imp

num_q, num_pos, num_imp, valid_contexts, valid_questions, valid_answers = get_data('spoken_test-v1.1.json')
print(len(valid_contexts))
print(len(valid_questions))
print(len(valid_answers))

def add_answer_at_end(answers, contexts):
    for answer, context in zip(answers, contexts):
        answer['text'] = answer['text'].lower()
        answer['answer_end'] = answer['answer_start'] + len(answer['text'])

add_answer_at_end(train_answers, train_contexts)
add_answer_at_end(valid_answers, valid_contexts)

token_lengths = []
token_lengths2 = []

for txt in train_questions:
    txt = txt.strip() 
    token_lengths2.append(len(txt.split(' ')))
    
for txt in train_contexts:
    txt = txt.strip()
    token_lengths.append(len(txt.split(' ')))

print(max(token_lengths))
print(max(token_lengths2))

plt.hist(token_lengths,  bins=20)
plt.ylabel('Count')
plt.xlabel('Length')
plt.title('Distribution of the Context Lengths');

plt.hist(token_lengths, bins=20, edgecolor='black', color='#a6cee3', alpha=0.8)

# Add axis labels and a title
plt.xlabel('X-axis: Length')
plt.ylabel('Y-axis: Count')
plt.title('Context Lengths Distributions')

# Add grid lines
plt.grid(axis='y', alpha=0.5)

# Show the plot
plt.show()

plt.hist(token_lengths2,  bins=20)
plt.ylabel('Count')
plt.xlabel('Length')
plt.title('Distribution of Question Lengths. ')

MAX_LENGTH = 250
MODEL_PATH = "bert-base-uncased"

print(train_questions[0:2])
print(train_contexts[0:2])

tokenizerFast = BertTokenizerFast.from_pretrained(MODEL_PATH)
train_encodings_fast = tokenizerFast(train_questions, train_contexts,  max_length = MAX_LENGTH, truncation=True, padding=True)
valid_encodings_fast = tokenizerFast(valid_questions,valid_contexts,  max_length = MAX_LENGTH, truncation=True, padding=True)
type(train_encodings_fast)
print(train_encodings_fast.keys())
print(valid_encodings_fast.keys())

print(len(train_encodings_fast['input_ids']))
print(len(train_encodings_fast['input_ids'][0]))

def return_Answer_startandend_train(idx):
    return_start = 0
    return_end = 0
    answer_encoding_fast = tokenizerFast(train_answers[idx]['text'],  max_length = MAX_LENGTH, truncation=True, padding=True)
    for a in range( len(train_encodings_fast['input_ids'][idx]) -  len(answer_encoding_fast['input_ids']) ): 
        match = True
        for i in range(1,len(answer_encoding_fast['input_ids']) - 1):
            if (answer_encoding_fast['input_ids'][i] != train_encodings_fast['input_ids'][idx][a + i]):
                match = False
                break
            if match:
                return_start = a+1
                return_end = a+i+1
                break
    return(return_start, return_end)

start_positions = []
end_positions = []
counter = 0
for t in range(len(train_encodings_fast['input_ids'])):
    s,e = return_Answer_startandend_train(t)
    start_positions.append(s)
    end_positions.append(e)
    if s==0:
        counter = counter + 1
train_encodings_fast.update({'start_positions': start_positions, 'end_positions': end_positions})
print(counter)

def return_answer_startend_valid(idx):
    return_start = 0
    return_end = 0
    answer_encoding_fast = tokenizerFast(valid_answers[idx]['text'],  max_length = MAX_LENGTH, truncation=True, padding=True)
    for a in range( len(valid_encodings_fast['input_ids'][idx])  -  len(answer_encoding_fast['input_ids'])   ): 
        match = True
        for i in range(1,len(answer_encoding_fast['input_ids']) - 1):
            if (answer_encoding_fast['input_ids'][i] != valid_encodings_fast['input_ids'][idx][a + i]):
                match = False
                break
            if match:
                return_start = a+1
                return_end = a+i+1
                break
    return(return_start, return_end)

start_positions = []
end_positions = []
counter = 0
for h in range(len(valid_encodings_fast['input_ids']) ):
   
    s, e = return_answer_startend_valid(h)
    start_positions.append(s)
    end_positions.append(e)
    if s==0:
        counter = counter + 1

valid_encodings_fast.update({'start_positions': start_positions, 'end_positions': end_positions})
print(counter)

class InputDataset(Dataset):
    def __init__(self, encodings):
        self.encodings = encodings
    def __getitem__(self, i):
        return {
            'input_ids': torch.tensor(self.encodings['input_ids'][i]),
            'token_type_ids': torch.tensor(self.encodings['token_type_ids'][i]),
            'attention_mask': torch.tensor(self.encodings['attention_mask'][i]),
            'start_positions': torch.tensor(self.encodings['start_positions'][i]),
            'end_positions': torch.tensor(self.encodings['end_positions'][i])
        }
    def __len__(self):
        return len(self.encodings['input_ids'])

train_dataset = InputDataset(train_encodings_fast)
valid_dataset = InputDataset(valid_encodings_fast)

train_data_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
valid_data_loader = DataLoader(valid_dataset, batch_size=1)

bert_model = BertModel.from_pretrained(MODEL_PATH)  #MODEL_PATH = "bert-base-uncased"

class QAModel(nn.Module):
    def __init__(self):
        super(QAModel, self).__init__()
        self.bert = bert_model
        self.drop_out = nn.Dropout(0.1)
        self.l1 = nn.Linear(768 * 2, 768 * 2)
        self.l2 = nn.Linear(768 * 2, 2)
        self.linear_relu_stack = nn.Sequential(
            self.drop_out,
            self.l1,
            nn.LeakyReLU(),
            self.l2 
        )
        
    def forward(self, input_ids, attention_mask, token_type_ids):
        model_output = self.bert(input_ids, attention_mask=attention_mask, token_type_ids=token_type_ids, output_hidden_states=True)
        hidden_states = model_output[2]
        out = torch.cat((hidden_states[-1], hidden_states[-3]), dim=-1)  
        logits = self.linear_relu_stack(out)
        start_logits, end_logits = logits.split(1, dim=-1)
        start_logits = start_logits.squeeze(-1)
        end_logits = end_logits.squeeze(-1)

        return start_logits, end_logits

model = QAModel()

def loss_function(start_logits, end_logits, start_positions, end_positions):
    loss_fct = nn.CrossEntropyLoss()
    start_loss = loss_fct(start_logits, start_positions)
    end_loss = loss_fct(end_logits, end_positions)
    total_loss = (start_loss + end_loss)/2
    return total_loss

def focal_loss_function(start_logits, end_logits, start_positions, end_positions, gamma):
    smax = nn.Softmax(dim=1)
    probs_start = smax(start_logits)
    inv_probs_start = 1 - probs_start
    probs_end = smax(end_logits)
    inv_probs_end = 1 - probs_end
    lsmax = nn.LogSoftmax(dim=1)
    log_probs_start = lsmax(start_logits)
    log_probs_end = lsmax(end_logits)
    
    nll = nn.NLLLoss()
    
    fl_start = nll(torch.pow(inv_probs_start, gamma)* log_probs_start, start_positions)
    fl_end = nll(torch.pow(inv_probs_end, gamma)*log_probs_end, end_positions)
    return ((fl_start + fl_end)/2)

optim = AdamW(model.parameters(), lr=2e-5, weight_decay=2e-2)
scheduler = ExponentialLR(optim, gamma=0.9)
total_acc = []
total_loss = []

def train_epoch(model, dataloader, epoch):
    model = model.train()
    losses = []
    acc = []
    counter = 0
    batch_tracker = 0
    for batch in tqdm(dataloader, desc = 'Running Epoch '):
        optim.zero_grad()
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        token_type_ids = batch['token_type_ids'].to(device)
        start_positions = batch['start_positions'].to(device)
        end_positions = batch['end_positions'].to(device)
        out_start, out_end = model(input_ids=input_ids, 
                attention_mask=attention_mask,
                token_type_ids=token_type_ids)
        
        loss = focal_loss_function(out_start, out_end, start_positions, end_positions,1) 
        losses.append(loss.item())
        loss.backward()
        optim.step()
        
        start_predictor = torch.argmax(out_start, dim=1)
        end_pred = torch.argmax(out_end, dim=1)
            
        acc.append(((start_predictor == start_positions).sum()/len(start_predictor)).item())
        acc.append(((end_pred == end_positions).sum()/len(end_pred)).item())
       
        batch_tracker = batch_tracker + 1
        if batch_tracker==250 and epoch==1:
            total_acc.append(sum(acc)/len(acc))
            loss_avg = sum(losses)/len(losses)
            total_loss.append(loss_avg)
            batch_tracker = 0
    scheduler.step()
    ret_acc = sum(acc)/len(acc)
    ret_loss = sum(losses)/len(losses)
    return(ret_acc, ret_loss)

def evaluate_model(model, dataloader):
    model = model.eval()
    losses = []
    acc = []
    counter = 0
    answer_list=[]
    with torch.no_grad():
        for batch in tqdm(dataloader, desc = 'Running the Evaluation'):
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            token_type_ids = batch['token_type_ids'].to(device)
            start_true = batch['start_positions'].to(device)
            end_true = batch['end_positions'].to(device)
            
            out_start, out_end = model(input_ids=input_ids, attention_mask=attention_mask,token_type_ids=token_type_ids)
            print("out_start",out_start.shape)
            start_predictor = torch.argmax(out_start)
            end_pred = torch.argmax(out_end)
            answer = tokenizerFast.convert_tokens_to_string(tokenizerFast.convert_ids_to_tokens(input_ids[0][start_predictor:end_pred]))
            tanswer = tokenizerFast.convert_tokens_to_string(tokenizerFast.convert_ids_to_tokens(input_ids[0][start_true[0]:end_true[0]]))
            answer_list.append([answer,tanswer])
        
    return answer_list

wer = load("wer")
EPOCHS = 3
model.to(device)
wer_list=[]
for epoch in range(EPOCHS):
    train_acc, train_loss = train_epoch(model, train_data_loader, epoch+1)
    print(f"Train Accuracy: {train_acc}      Train Loss: {train_loss}")
    answer_list = evaluate_model(model, valid_data_loader)
    pred_answers=[]
    true_answers=[]
    for i in range(len(answer_list)):
        if(len(answer_list[i][0])==0):
            answer_list[i][0]="$"
        if(len(answer_list[i][1])==0):
            answer_list[i][1]="$"
        pred_answers.append(answer_list[i][0])
        true_answers.append(answer_list[i][1])
    wer_score = wer.compute(predictions=pred_answers, references=true_answers)
    wer_list.append(wer_score)
print(wer_list)

tokens = tokenizerFast.tokenize("The quick brown fox jumps over the lazy dog.")
print(tokens)
output = tokenizerFast.convert_tokens_to_string(tokens)
print(output)

