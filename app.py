# -*- coding: utf-8 -*-
import os
import sys
import tensorflow as tf
import numpy as np
import data_utils
from translate import Transliteration
from flask import Flask, request, jsonify

transliteration = Transliteration()

app = Flask(__name__)  # Flask 객체 선언, 파라미터로 어플리케이션 패키지의 이름을 넣어 준다.
app.config['JSON_AS_ASCII'] = False # 한글 데이터 전송을 위해서 설정해 준다.

@app.route("/transliterate", methods=['GET'])
def transliterate():

  input = request.args.get('input')
  
  output = transliteration.run(input)
  learned = transliteration.is_learned(input)
  print(input, learned)
  return jsonify(output)

if __name__ == "__main__":
  app.run(debug = True, host='0.0.0.0', port=80, use_reloader=False)

