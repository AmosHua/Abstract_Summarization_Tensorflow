import tensorflow as tf
import logging.config
import tensorflow.contrib.seq2seq as s2s
import tensorflow.contrib as contrib
import tensorflow.contrib.rnn as rnn
import numpy as np

LOG_FILE = './log/seq2seq.log'
MODEL_FILE = './model/'
handler = logging.FileHandler(LOG_FILE, mode='w')  # 实例化handler
fmt = '%(asctime)s - %(filename)s:%(lineno)s - %(name)s - %(message)s'
formatter = logging.Formatter(fmt)  # 实例化formatter
handler.setFormatter(formatter)  # 为handler添加formatter
logger = logging.getLogger('seq2seqlogger')  # 获取名为tst的logger
logger.addHandler(handler)  # 为logger添加handler
logger.setLevel(logging.DEBUG)


class seq2seqmodel:
    def __init__(self, vocab_size, embed_size, encoder_hidden_units, decoder_hidden_units, batch_size,
                 embed_matrix_init, encoder_layers, learning_rate):
        self.vocab_size = vocab_size
        self.embed_size = embed_size
        self.encoder_hidden_units = encoder_hidden_units
        self.decoder_hidden_units = decoder_hidden_units * 2
        self.batch_size = batch_size
        self.embed_matrix_init = embed_matrix_init
        self.encoder_layers = encoder_layers
        self.learning_rate = learning_rate

    def _create_placeholder(self):
        with tf.name_scope("data_seq2seq"):
            self.encoder_inputs = tf.placeholder(shape=(self.batch_size, None), dtype=tf.int32, name='encoder_inputs')
            self.decoder_inputs = tf.placeholder(shape=(self.batch_size, None), dtype=tf.int32, name='decoder_inputs')
            self.decoder_targets = tf.placeholder(shape=(self.batch_size, None), dtype=tf.int32, name='decoder_targets')
            # self.encoder_length = tf.placeholder(shape=self.batch_size, dtype=tf.int32, name='encoder_length')
            self.decoder_length = tf.placeholder(shape=self.batch_size, dtype=tf.int32, name='decoder_length')

    def _create_embedding(self):
        self.embeddings_trainable = tf.Variable(initial_value=self.embed_matrix_init, name='word_embedding_train')
        # self.encoder_inputs = tf.unstack(self.encoder_inputs)
        # self.encoder_inputs_embedded = [tf.nn.embedding_lookup(self.embeddings_trainable, x) for x in
        #                                 self.encoder_inputs]
        self.encoder_inputs_embedded = tf.nn.embedding_lookup(self.embeddings_trainable, self.encoder_inputs)
        self.decoder_inputs_embedded = tf.nn.embedding_lookup(self.embeddings_trainable, self.decoder_inputs)

    def _create_cell(self):

        for layer_i in range(self.encoder_layers):
            with tf.variable_scope('encoder%i' % layer_i, reuse=tf.AUTO_REUSE):
                cell_fw = rnn.LSTMCell(
                    num_units=self.encoder_hidden_units,
                    initializer=tf.random_uniform_initializer(-0.1, 0.1, seed=114),
                    state_is_tuple=True)
                cell_bw = rnn.LSTMCell(
                    num_units=self.encoder_hidden_units,
                    initializer=tf.random_uniform_initializer(-0.1, 0.1, seed=133),
                    state_is_tuple=True)
                (self.encoder_inputs_embedded, self.encoder_final_state) = tf.nn.bidirectional_dynamic_rnn(
                    cell_fw=cell_fw,
                    cell_bw=cell_bw,
                    inputs=self.encoder_inputs_embedded,
                    dtype=tf.float32)
        self.encoder_final_state_c = tf.concat(
            (self.encoder_final_state[0].c, self.encoder_final_state[1].c), 1)

        self.encoder_final_state_h = tf.concat(
            (self.encoder_final_state[0].h, self.encoder_final_state[1].h), 1)

        self.encoder_final_state = contrib.rnn.LSTMStateTuple(
            c=self.encoder_final_state_c,
            h=self.encoder_final_state_h)
        print(self.encoder_final_state)

        # with tf.variable_scope('encoder', reuse=tf.AUTO_REUSE):
        #     encoder_cell = tf.nn.rnn_cell.LSTMCell(num_units=self.encoder_hidden_units, name='encoder_cell')
        #
        #     self.encoder_output, self.encoder_final_state = tf.nn.dynamic_rnn(
        #         cell=encoder_cell,
        #         inputs=self.encoder_inputs_embedded,
        #         dtype=tf.float32,
        #         time_major=False
        #     )
        # print(self.encoder_final_state)

        with tf.variable_scope('decoder', reuse=tf.AUTO_REUSE):
            self.decoder_cell = tf.nn.rnn_cell.LSTMCell(num_units=self.decoder_hidden_units,
                                                        name='decoder_cell',
                                                        state_is_tuple=True)
            self.fc_layer = tf.layers.Dense(self.vocab_size, name='dense_layer')

            self.helper_train = contrib.seq2seq.TrainingHelper(inputs=self.decoder_inputs_embedded,
                                                               sequence_length=self.decoder_length,
                                                               name="decode_training_helper")
            self.decoder_train = contrib.seq2seq.BasicDecoder(cell=self.decoder_cell,
                                                              initial_state=self.encoder_final_state,
                                                              helper=self.helper_train,
                                                              output_layer=self.fc_layer
                                                              )
            self.decoder_train_logits, _, _ = s2s.dynamic_decode(decoder=self.decoder_train
                                                                 )

            self.start_tokens = [18498 for i in range(self.batch_size)]
            self.end_tokens = 0

            self.helper_infer = contrib.seq2seq.GreedyEmbeddingHelper(embedding=self.embeddings_trainable,
                                                                      start_tokens=self.start_tokens,
                                                                      end_token=self.end_tokens)
            self.decoder_infer = contrib.seq2seq.BasicDecoder(cell=self.decoder_cell,
                                                              initial_state=self.encoder_final_state,
                                                              helper=self.helper_infer,
                                                              output_layer=self.fc_layer)
            self.decoder_infer_logits, _, _ = s2s.dynamic_decode(self.decoder_infer,
                                                                 maximum_iterations=20
                                                                 )

        #
        #     self.decoder_outputs_train, _ = tf.nn.dynamic_rnn(
        #         cell=decoder_cell,
        #         inputs=self.decoder_inputs_embedded,
        #         initial_state=self.encoder_final_state,
        #         dtype=tf.float32,
        #         sequence_length=self.decoder_length,
        #         time_major=False)
        #
        #     start_tokens = 0
        #     end_tokens = 0
        #
        #     # Helper
        #     helper = s2s.GreedyEmbeddingHelper(
        #         self.embeddings_trainable,
        #         tf.fill([self.batch_size], start_tokens), end_tokens)
        #     # Decoder
        #     decoder = s2s.BasicDecoder(
        #         decoder_cell, helper, self.encoder_final_state)
        #     # Dynamic decoding
        #     decoder_infer_outputs, _, _ = s2s.dynamic_decode(
        #         decoder, maximum_iterations=25)
        #     self.decoder_prediction = decoder_infer_outputs.sample_id

    def _create_loss(self):
        """use linear layer to project the output of decoder to predict the ouput word"""
        with tf.name_scope("loss"):
            # self.decoder_logits_test = tf.contrib.layers.linear(self.decoder_outputs_test, self.vocab_size)
            # self.decoder_prediction = tf.argmax(self.decoder_logits_test, 2)

            # self.targets = tf.reshape(self.decoder_targets, [-1])
            # self.logits_flat = tf.reshape(self.decoder_train_logits.rnn_output, [-1, self.vocab_size])

            self.targets = self.decoder_targets
            self.targets = tf.one_hot(self.targets, depth=self.vocab_size, dtype=tf.float32)
            self.logits_flat = self.decoder_train_logits.rnn_output

            # self.logits_flat = tf.argmax(self.logits_flat, 0)

            # self.stepwise_cross_entropy = tf.nn.softmax_cross_entropy_with_logits_v2(
            #     labels=tf.one_hot(self.decoder_targets,
            #                       depth=self.vocab_size,
            #                       dtype=tf.float32),
            #     logits=self.model_outputs,
            # )
            # self.loss = tf.reduce_mean(self.stepwise_cross_entropy)

            # self.loss = tf.losses.sparse_softmax_cross_entropy(self.targets, self.logits_flat)

            self.loss = tf.losses.softmax_cross_entropy(onehot_labels=self.targets,
                                                        logits=self.logits_flat)

            self.optimizer = tf.train.AdamOptimizer(learning_rate=self.learning_rate).minimize(self.loss)

    def _create_summaries(self):
        with tf.name_scope("summaries_seq2seq"):
            tf.summary.scalar("loss", self.loss)
            tf.summary.histogram("histogram loss", self.loss)
            self.summary_op = tf.summary.merge_all()

    def _build_graph(self):
        self._create_placeholder()
        self._create_embedding()
        self._create_cell()
        self._create_loss()
        self._create_summaries()
        print("seq2seq graph built")

    def _train(self, epoch, num_train_steps, batches, skip_steps):
        saver = tf.train.Saver(tf.trainable_variables(), max_to_keep=3)
        with tf.Session() as sess:
            sess.run(tf.global_variables_initializer())
            self.total_loss = 0.0
            print("start training seq2seq model")
            writer = tf.summary.FileWriter('./graphs/seq2seq', sess.graph)
            for i in range(epoch):
                for index in range(num_train_steps):
                    print("epoch: %d at train step: %d" % (i, index + 1))
                    encoder_inputs, decoder_inputs, decoder_targets, encoder_length, decoder_length = next(batches)
                    decoder_length = [30 for i in range(self.batch_size)]
                    feed_dict = {
                        self.decoder_targets: decoder_targets,
                        # self.encoder_length: encoder_length,
                        self.decoder_length: decoder_length,
                        self.encoder_inputs: encoder_inputs,
                        self.decoder_inputs: decoder_inputs
                    }
                    loss_batch, _, summary = sess.run([self.loss, self.optimizer, self.summary_op],
                                                      feed_dict=feed_dict)
                    self.total_loss += loss_batch
                    writer.add_summary(summary, global_step=index)
                    if (index + 1) % skip_steps == 0:
                        logger.debug('seq2seq average loss at epoch {} step {} : {:8.6f}'.format(i, index + 1,
                                                                                                 self.total_loss / skip_steps))
                        self.total_loss = 0.0
                saver.save(sess, MODEL_FILE + 'model.ckpt', global_step=i * 220 + num_train_steps)
                logger.debug("seq2seq trained,model saved at epoch {} step {}".format(i, num_train_steps))

    def _test(self, num_train_steps, batches, one_hot_dictionary_index):
        saver = tf.train.Saver(tf.trainable_variables(), max_to_keep=5)
        ckpt = tf.train.get_checkpoint_state(MODEL_FILE)
        with tf.Session() as sess:
            if ckpt and ckpt.model_checkpoint_path:
                saver.restore(sess, ckpt.model_checkpoint_path)
                print("the model has been successfully restored")
                # sess.run(tf.global_variables_initializer())
                for index in range(num_train_steps):
                    encoder_inputs, decoder_inputs, decoder_targets, encoder_length, decoder_length = next(batches)
                    decoder_length = [30 for i in range(self.batch_size)]
                    feed_dict = {
                        self.decoder_targets: decoder_targets,
                        # self.encoder_length: encoder_length,
                        self.decoder_length: decoder_length,
                        self.encoder_inputs: encoder_inputs,
                        self.decoder_inputs: decoder_inputs
                    }
                    # print("article:")
                    # print(encoder_inputs[0])

                    print("infer headline: ")
                    prediction = sess.run(self.decoder_infer_logits, feed_dict=feed_dict)
                    print(prediction)

                    print("logits_flat")
                    logits_flat = sess.run(self.decoder_train_logits, feed_dict=feed_dict)
                    logits_flat = logits_flat.rnn_output
                    logits_flat = np.argmax(logits_flat, 2)
                    logits_flat = logits_flat[0]
                    answer = [one_hot_dictionary_index[i] for i in logits_flat]
                    print(answer)

                    print("targets")
                    targets = sess.run(self.decoder_targets, feed_dict=feed_dict)
                    targets = targets[0]
                    answer = [one_hot_dictionary_index[i] for i in targets]
                    print(answer)
            else:
                print("model restored failed")
                pass