# -*-  coding: utf-8 -*-
#
# Copyright 2015 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================

# Copied from https://github.com/tensorflow/tensorflow/blob/r0.8/tensorflow/models/rnn/translate/translate.py

"""Binary for training translation models and decoding from them.

Running this program without --decode will download the WMT corpus into
the directory specified as --data_dir and tokenize it in a very basic way,
and then start training a model saving checkpoints to --train_dir.

Running with --decode starts an interactive loop so you can see how
the current checkpoint translates English sentences into French.

See the following papers for more information on neural translation models.
 * http://arxiv.org/abs/1409.3215
 * http://arxiv.org/abs/1409.0473
 * http://arxiv.org/abs/1412.2007
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from openpyxl import load_workbook

import math
import os
import random
import sys
import time
import subprocess
import re

import numpy as np
from six.moves import xrange  # pylint: disable=redefined-builtin
import tensorflow as tf
import time
import data_utils
from tensorflow.models.rnn.translate import seq2seq_model


tf.app.flags.DEFINE_float("learning_rate", 0.5, "Learning rate.")
tf.app.flags.DEFINE_float("learning_rate_decay_factor", 0.99,
                          "Learning rate decays by this much.")
tf.app.flags.DEFINE_float("max_gradient_norm", 5.0,
                          "Clip gradients to this norm.")
tf.app.flags.DEFINE_integer("batch_size", 64,
                            "Batch size to use during training.")
tf.app.flags.DEFINE_integer("size", 128, "Size of each model layer.")
tf.app.flags.DEFINE_integer("num_layers", 2, "Number of layers in the model.")
tf.app.flags.DEFINE_integer("en_vocab_size", 40, "English vocabulary size.")
tf.app.flags.DEFINE_integer("fr_vocab_size", 1000, "French vocabulary size.")
tf.app.flags.DEFINE_string("data_dir", "data", "Data directory")
tf.app.flags.DEFINE_string("train_dir", "train", "Training directory.")
tf.app.flags.DEFINE_integer("max_train_data_size", 0,
                            "Limit on the size of training data (0: no limit).")
tf.app.flags.DEFINE_integer("steps_per_checkpoint", 100,
                            "How many training steps to do per checkpoint.")
tf.app.flags.DEFINE_boolean("decode", False,
                            "Set to True for interactive decoding.")
tf.app.flags.DEFINE_boolean("self_test", False,
                            "Run a self-test if this is set to True.")
tf.app.flags.DEFINE_boolean("use_lstm", True,
                            "Set to True for using lstm instead gru cell.")

FLAGS = tf.app.flags.FLAGS

# We use a number of buckets and pad to the closest one for efficiency.
# See seq2seq_model.Seq2SeqModel for details of how they work.
#_buckets = [(5, 10), (10, 15), (20, 25), (40, 50)]
_buckets = [(7, 5), (10, 7), (17, 10), (37, 20)]
# _buckets = [(10, 5), (15, 10), (20, 15), (25, 20), (30 , 25), (35, 30), (40, 35), (45, 40), (55, 50), (60, 55), (65, 60), (70, 65), (75, 70), (80, 75), (85, 80), (90, 85), (95, 90), (100, 95), (105, 100), (110, 105), (115, 110), (120, 115), (125, 120), (130, 125), (135, 130), (140, 135), (200, 140)]




def read_data(source_path, target_path, max_size=None):
  """Read data from source and target files and put into buckets.

  Args:
    source_path: path to the files with token-ids for the source language.
    target_path: path to the file with token-ids for the target language;
      it must be aligned with the source file: n-th line contains the desired
      output for n-th line from the source_path.
    max_size: maximum number of lines to read, all other will be ignored;
      if 0 or None, data files will be read completely (no limit).

  Returns:
    data_set: a list of length len(_buckets); data_set[n] contains a list of
      (source, target) pairs read from the provided data files that fit
      into the n-th bucket, i.e., such that len(source) < _buckets[n][0] and
      len(target) < _buckets[n][1]; source and target are lists of token-ids.
  """
  data_set = [[] for _ in _buckets]
  diffs = []
  with tf.gfile.GFile(source_path, mode="r") as source_file:
    with tf.gfile.GFile(target_path, mode="r") as target_file:
      source, target = source_file.readline(), target_file.readline()
      counter = 0
      while source and target and (not max_size or counter < max_size):
        counter += 1
        if counter % 100000 == 0:
          print("  reading data line %d" % counter)
          sys.stdout.flush()
        source_ids = [int(x) for x in source.split()]
        target_ids = [int(x) for x in target.split()]
        target_ids.append(data_utils.EOS_ID)
        for bucket_id, (source_size, target_size) in enumerate(_buckets):
          if len(source_ids) < source_size and len(target_ids) < target_size:
            data_set[bucket_id].append([source_ids, target_ids])
            diffs.append(source_size - len(source_ids) + target_size - len(target_ids))
            break
        source, target = source_file.readline(), target_file.readline()
  #print("mean padding count: %f" % np.mean(diffs))
  return data_set


def create_model(session, forward_only):
  """Create translation model and initialize or load parameters in session."""
  # print(FLAGS.train_dir) # train
  if not os.path.exists(FLAGS.train_dir):
    os.mkdir(FLAGS.train_dir)
  print('Step 1 : Create transliteration model')
  model = seq2seq_model.Seq2SeqModel(
      FLAGS.en_vocab_size, FLAGS.fr_vocab_size, _buckets,
      FLAGS.size, FLAGS.num_layers, FLAGS.max_gradient_norm, FLAGS.batch_size,
      FLAGS.learning_rate, FLAGS.learning_rate_decay_factor,
      forward_only=forward_only, use_lstm=FLAGS.use_lstm)
  
  ckpt = tf.train.get_checkpoint_state(FLAGS.train_dir)
  print('Step 2 : Confirm checkpoint parameters')
  # print(ckpt) # checkpoint
  # print(ckpt.model_checkpoint_path) # check
  if ckpt and tf.gfile.Exists(ckpt.model_checkpoint_path + '.index'):
    print("Step 3 : Reading model parameters from %s" % ckpt.model_checkpoint_path)
    model.saver.restore(session, ckpt.model_checkpoint_path)
  else:
    print("Created model with fresh parameters.")
    session.run(tf.global_variables_initializer())
  return model


def train():
  """Train a en->fr translation model using WMT data."""
  # Prepare WMT data.
  print("Preparing WMT data in %s" % FLAGS.data_dir) 
  en_train, fr_train, en_dev, fr_dev, _, _ = data_utils.prepare_wmt_data(
      FLAGS.data_dir, FLAGS.en_vocab_size, FLAGS.fr_vocab_size)

  
  with tf.Session() as sess:
    # Create model.
    print("Creating %d layers of %d units." % (FLAGS.num_layers, FLAGS.size))
    model = create_model(sess, False)

    # Read data into buckets and compute their sizes.
    print ("Reading development and training data (limit: %d)."
           % FLAGS.max_train_data_size)
    dev_set = read_data(en_dev, fr_dev)
    train_set = read_data(en_train, fr_train, FLAGS.max_train_data_size)
#    for bucket_id, (source_size, target_size) in enumerate(_buckets):
#      print("data set index %d count: %d" % (bucket_id, len(train_set[bucket_id])))
    train_bucket_sizes = [len(train_set[b]) for b in xrange(len(_buckets))]
    train_total_size = float(sum(train_bucket_sizes))

    # A bucket scale is a list of increasing numbers from 0 to 1 that we'll use
    # to select a bucket. Length of [scale[i], scale[i+1]] is proportional to
    # the size if i-th training bucket, as used later.
    train_buckets_scale = [sum(train_bucket_sizes[:i + 1]) / train_total_size
                           for i in xrange(len(train_bucket_sizes))]

    # This is the training loop.
    step_time, loss = 0.0, 0.0
    current_step = 0
    previous_losses = []
    best_eval_ppx = float('inf')
    while True:
      # Choose a bucket according to data distribution. We pick a random number
      # in [0, 1] and use the corresponding interval in train_buckets_scale.
      random_number_01 = np.random.random_sample()
      bucket_id = min([i for i in xrange(len(train_buckets_scale))
                       if train_buckets_scale[i] > random_number_01])

      # Get a batch and make a step.
      start_time = time.time()
      encoder_inputs, decoder_inputs, target_weights = model.get_batch(
          train_set, bucket_id)
      _, step_loss, _ = model.step(sess, encoder_inputs, decoder_inputs,
                                   target_weights, bucket_id, False)
      step_time += (time.time() - start_time) / FLAGS.steps_per_checkpoint
      loss += step_loss / FLAGS.steps_per_checkpoint
      current_step += 1

      # Once in a while, we save checkpoint, print statistics, and run evals.
      if current_step % FLAGS.steps_per_checkpoint == 0:
        # Print statistics for the previous epoch.
        perplexity = math.exp(loss) if loss < 300 else float('inf')
        print ("global step %d learning rate %.4f step-time %.2f perplexity "
               "%.2f" % (model.global_step.eval(), model.learning_rate.eval(),
                         step_time, perplexity))
        # Decrease learning rate if no improvement was seen over last 3 times.
        if len(previous_losses) > 2 and loss > max(previous_losses[-3:]):
          sess.run(model.learning_rate_decay_op)
        previous_losses.append(loss)
        # Save checkpoint and zero timer and loss.
        checkpoint_path = os.path.join(FLAGS.train_dir, "translate.ckpt")
        model.saver.save(sess, checkpoint_path, global_step=model.global_step)
        step_time, loss = 0.0, 0.0
        # Run evals on development set and print their perplexity.
        eval_ppx_list = []
        for bucket_id in xrange(len(_buckets)):
          if len(dev_set[bucket_id]) == 0:
            print("  eval: empty bucket %d" % (bucket_id))
            continue
          encoder_inputs, decoder_inputs, target_weights = model.get_batch(
              dev_set, bucket_id)
          _, eval_loss, _ = model.step(sess, encoder_inputs, decoder_inputs,
                                       target_weights, bucket_id, True)
          eval_ppx = math.exp(eval_loss) if eval_loss < 300 else float('inf')
          eval_ppx_list.append(eval_ppx)
          print("  eval: bucket %d perplexity %.2f" % (bucket_id, eval_ppx))
        sys.stdout.flush()

        mean_eval_ppx = np.mean(eval_ppx_list)
        if mean_eval_ppx < best_eval_ppx:
          best_eval_ppx = mean_eval_ppx
          print("BEST mean eval perplexity: %.3f" % best_eval_ppx)
# 9701

def decode():
  load_wb = load_workbook('./test_xlsx/testfile.xlsx', data_only = True)
  load_ws = load_wb['melon_song']

  get_cells = load_ws['D2' : 'D10']
  outputs = []
  print("Step 4 : Transliteration Start")
  for row in get_cells:
   for cell in row:   
      sentence = cell.value.strip()
      if sentence:
      # 모델에 개체명을 넣어서 나온 결과 값
        output = transliteration.run(sentence)
        outputs.append(output)
      # 학습된 데이터 인지 체크
        learned = transliteration.is_learned(sentence)
        sys.stdout.flush()
  outputs = []
  start = time.time()
  # 학습된 모델 불러오기
  transliteration = Transliteration()
  # 원하는 열,행 범위 설정
  get_cells = load_ws['D2' : 'D20']
  print("Step 4 : 영어-한글 변환 결과 출력")
  for row in get_cells:
    for cell in row:   
      sentence = cell.value.strip()
      if sentence:
        # 모델에 개체명을 넣어서 나온 결과 값
        output = transliteration.run(sentence)
        # 학습된 데이터 인지 체크
        learned = transliteration.is_learned(sentence)
        sys.stdout.flush()
          # if not learned:
          #   print("(%s is not trained word)" % sentence)

      # sentence : 개체명
      # output : 모델에 개체명을 넣어서 나온 값
      outputs.append(output)
      print('Input :', sentence, '/ Ouput : ', output)
  print("Output-Time : ", ((time.time() - start))/60 , "Output-Data-Numbers : ", len(outputs))

def self_test():
  """Test the translation model."""
  with tf.Session() as sess:
    print("Self-test for neural translation model.")
    # Create model with vocabularies of 10, 2 small buckets, 2 layers of 32.
    model = seq2seq_model.Seq2SeqModel(10, 10, [(3, 3), (6, 6)], 32, 2,
                                       5.0, 32, 0.3, 0.99, num_samples=8)
    sess.run(tf.global_variables_initializer())
   
    # Fake data set for both the (3, 3) and (6, 6) bucket.
    data_set = ([([1, 1], [2, 2]), ([3, 3], [4]), ([5], [6])],
                [([1, 1, 1, 1, 1], [2, 2, 2, 2, 2]), ([3, 3, 3], [5, 6])])
    for _ in xrange(5):  # Train the fake model for 5 steps.
      bucket_id = random.choice([0, 1])
      encoder_inputs, decoder_inputs, target_weights = model.get_batch(
          data_set, bucket_id)
      model.step(sess, encoder_inputs, decoder_inputs, target_weights,
                 bucket_id, False)


class Transliteration:
  FNULL = open(os.devnull, 'w')

  def __init__(self):
    self.sess = tf.Session()
    self.download_trained_if_not_exists()
    # Create model and load parameters.
    self.model = create_model(self.sess, True)
    self.model.batch_size = 1  # We decode one sentence at a time.
    # Load vocabularies.
    # print(FLAGS.data_dir) / data
    en_vocab_path = os.path.join(FLAGS.data_dir,
                                 "vocab%d.en" % FLAGS.en_vocab_size)
    # print(en_vocab_path) / data/vocab40.en
    fr_vocab_path = os.path.join(FLAGS.data_dir,
                                 "vocab%d.fr" % FLAGS.fr_vocab_size)
    # print(fr_vocab_path) / data/vocab1000.fr
    self.en_vocab, _ = data_utils.initialize_vocabulary(en_vocab_path)
    _, self.rev_fr_vocab = data_utils.initialize_vocabulary(fr_vocab_path)

  def has_trained(self):
    # print(FLAGS.train_dir) / train
    checkpoint_path = os.path.join(FLAGS.train_dir, "checkpoint")
    return os.path.isfile(checkpoint_path)

  def download_trained_if_not_exists(self):
    if self.has_trained():
      return
    print('No trained files, download the files..')
    subprocess.call(['mkdir', '-p', FLAGS.train_dir])
    for f in ['checkpoint', 'translate.ckpt-32900', 'translate.ckpt-32900.meta']:
      subprocess.call(['curl', ('https://raw.githubusercontent.com/muik/transliteration-files/master/%s' % f), '-o', ('train/%s' % f)])

  def is_learned(self, input):
    path = os.path.join(FLAGS.data_dir, "giga-fren.release2.en")
    return 0 == subprocess.call(['grep', '-i', '^%s$' % input, path], stdout=self.FNULL)

  def run(self, sentence):
    # Get token-ids for the input sentence.
    token_ids = data_utils.sentence_to_token_ids(sentence, self.en_vocab)
    # Which bucket does it belong to?
    bucket_id = min(b for b in xrange(len(_buckets)) if _buckets[b][0] > len(token_ids) )  
    # Get a 1-element batch to feed the sentence to the model.
    encoder_inputs, decoder_inputs, target_weights = self.model.get_batch(
        {bucket_id: [(token_ids, [])]}, bucket_id)
    # Get output logits for the sentence.
    _, _, output_logits = self.model.step(self.sess, encoder_inputs, decoder_inputs,
                                     target_weights, bucket_id, True)
    # This is a greedy decoder - outputs are just argmaxes of output_logits.
    outputs = [int(np.argmax(logit, axis=1)) for logit in output_logits]
    # If there is an EOS symbol in outputs, cut them at that point.
    if data_utils.EOS_ID in outputs:
      outputs = outputs[:outputs.index(data_utils.EOS_ID)]
    # Print out French sentence corresponding to outputs.
    return "".join([self.rev_fr_vocab[output] for output in outputs])


def main(_):
  if FLAGS.self_test:
    self_test()
  elif FLAGS.decode:
    decode()
  else:
    train()

if __name__ == "__main__":
  tf.app.run()

