# English-Korean Transliteration

영어-한글 표기 변환기(Transliteration)는 영어 단어를 한글 표기로 변환 하는 프로그램입니다.

동작 방법은 기계 학습으로 (영어단어, 한글표기) 쌍의 수많은 데이터를 학습한 결과대로 변환을 수행합니다.

##### 주 학습 데이터

- 국립국어원의 [외래어 표기법의 용례](http://www.korean.go.kr/front/foreignSpell/foreignSpellList.do?mn_id=96)
- 위키낱말사전의 [한국어 외래어](https://ko.wiktionary.org/wiki/%EB%B6%84%EB%A5%98:%ED%95%9C%EA%B5%AD%EC%96%B4_%EC%99%B8%EB%9E%98%EC%96%B4)

학습에 필요한 양질의 대량 데이터가 필요합니다.

## 요구 사항 (Requirements)

- Python 2.7.16
- tensorflow 0.12.0
- Flask 1.1.2
- werkzeug 1.0.1
-

## 모델 학습 하기 (Run train)

```bash
$ python translate.py
Preparing WMT data in data
Creating 2 layers of 128 units.
Created model with fresh parameters.
Reading development and training data (limit: 0).
global step 100 learning rate 0.5000 step-time 0.38 perplexity 240.07
  eval: bucket 0 perplexity 124.96
  eval: bucket 1 perplexity 136.77
  eval: bucket 2 perplexity 146.66
  eval: bucket 3 perplexity 142.27
global step 200 learning rate 0.5000 step-time 0.34 perplexity 80.28
  eval: bucket 0 perplexity 62.63
  eval: bucket 1 perplexity 53.76
  eval: bucket 2 perplexity 95.01
  eval: bucket 3 perplexity 105.53
...
```

ubuntu 20.04

## Run Flask Web API

Mac OS 와 Linux.

```bash
$ python app.py
Step 1 : Create transliteration model
Step 2 : Confirm checkpoint parameters
Step 3 : Reading model parameters from train/translate.ckpt-81000
 * Serving Flask app "app" (lazy loading)
 * Environment: production
   WARNING: This is a development server. Do not use it in a production deployment.
   Use a production WSGI server instead.
 * Debug mode: on
 * Running on http://0.0.0.0:80/ (Press CTRL+C to quit)
```
