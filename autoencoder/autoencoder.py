# Inspired by the TF Tutorial: https://www.tensorflow.org/get_started/mnist/pros

import tensorflow as tf
import numpy as np

# Mnist Data
from tensorflow.examples.tutorials.mnist import input_data as mnist_data

# Constants to eventually parameterise
BASE_LOGDIR = './logs/'
RUN = 'beta1-reconf'
LEARN_RATE = 1e-4
BATCH_SIZE = 2048
MAX_EPOCHS = 10000
output_steps = 20
latent_size = 10
beta = 0

# Activation function to use for layers
#act_func = tf.nn.softplus
act_func = tf.nn.tanh

# Enable or disable GPU
SESS_CONFIG = tf.ConfigProto(device_count = {'GPU': 1})

# Define variable functions
def weight_variable(shape, name="W"):
    initial = tf.truncated_normal(shape, stddev=0.1)
    return tf.Variable(initial, name=name)

def bias_variable(shape, name="B"):
    initial = tf.constant(0.1, shape=shape)
    return tf.Variable(initial, name=name)



# Get Data
mnist = mnist_data.read_data_sets("MNIST_data/", one_hot=True)
MAX_TRAIN_STEPS = int(MAX_EPOCHS*mnist.train.num_examples/BATCH_SIZE)
SIZE_X = 28
SIZE_Y = 28
NUM_CLASSES = 10 

with tf.name_scope('MainGraph'):
    with tf.name_scope('Inputs'):
        # Placeholders for data and labels
        x = tf.placeholder(tf.float32, shape=[None, SIZE_X*SIZE_Y])
        y_true = tf.placeholder(tf.float32, shape=[None, NUM_CLASSES])

        # Reshape X to make it into a 2D image
        x_image = tf.reshape(x, [-1, SIZE_X, SIZE_Y, 1])
        tf.summary.image('original_image', x_image, 3)


    # FC Encoder Layers
    with tf.name_scope('encoder_FC1'):
        W_fc1 = weight_variable([SIZE_X*SIZE_Y, 512])
        b_fc1 = bias_variable([512]) 
        h_fc1 = act_func(tf.matmul(x, W_fc1) + b_fc1)
        tf.summary.histogram('W_fc1', W_fc1)
        tf.summary.histogram('b_fc1', b_fc1)

    with tf.name_scope('encoder_FC2'):
        W_fc2 = weight_variable([512, 512])
        b_fc2 = bias_variable([512])
        tf.summary.histogram('W_fc2', W_fc2)
        tf.summary.histogram('b_fc2', b_fc2)
        h_fc2 = tf.matmul(h_fc1, W_fc2) + b_fc2

    with tf.name_scope('encoder_latent'):
        W_fc_mu = weight_variable([512, latent_size])
        W_fc_sigma = weight_variable([512, latent_size])
        b_fc_mu = bias_variable([latent_size])
        b_fc_sigma = bias_variable([latent_size])
        latent_mu = tf.matmul(h_fc2, W_fc_mu) + b_fc_mu
        latent_sigma = tf.matmul(h_fc2, W_fc_sigma) + b_fc_sigma

    with tf.name_scope('latent_space'):
        log_sigma = tf.nn.softplus(latent_sigma) + 1e-6 
        tf.summary.histogram('latent_mu', latent_mu)
        tf.summary.histogram('latent_sigma', latent_sigma)
        # Generate the noise component epsilon as a standard normal RV
        epsilon = tf.random_normal(tf.shape(latent_mu), 0, 1, dtype=tf.float32)
        z = latent_mu + tf.exp(log_sigma)*epsilon

    with tf.name_scope('decoder_FC1'):
        W_fc_up1 = weight_variable([latent_size, 512])
        b_fc_up1 = bias_variable([512])
        h_fc_up1 = act_func(tf.matmul(z, W_fc_up1) + b_fc_up1)

    with tf.name_scope('decoder_FC2'):
        W_fc_up2 = weight_variable([512, SIZE_X*SIZE_Y])
        b_fc_up2 = bias_variable([SIZE_X*SIZE_Y])
        #gen_vec = act_func(tf.matmul(h_fc_up1, W_fc_up2) + b_fc_up2)
        gen_vec = tf.sigmoid(tf.matmul(h_fc_up1, W_fc_up2) + b_fc_up2)
        # Reshape and display
        gen_img = tf.reshape(gen_vec, [-1, SIZE_X, SIZE_Y, 1])
        tf.summary.image('Generated_Image', gen_img, 3)

    with tf.name_scope('Objective'):
        with tf.name_scope('KLD'):
            # Generate KL-Divergence Loss
            batch_kl_div = log_sigma + (tf.exp(log_sigma)+latent_mu*latent_mu)/(2*(tf.exp(log_sigma)*tf.exp(log_sigma))) - 0.5

            kl_div = tf.reduce_sum(batch_kl_div)
            tf.summary.scalar('KL-Divergence', kl_div)

        with tf.name_scope('Generation_Loss'):
            generation_loss = tf.losses.mean_squared_error(gen_vec, x)
            tf.summary.scalar('generation_loss', generation_loss)

        total_loss = generation_loss + beta*kl_div 

        tf.summary.scalar('Total_Loss', total_loss)


# Define the training step
train_step = tf.train.AdamOptimizer(LEARN_RATE).minimize(total_loss)

# Create the session
sess = tf.Session(config=SESS_CONFIG)

# Init all weights
sess.run(tf.global_variables_initializer())

# Merge Summaries and Create Summary Writer for TB
all_summaries = tf.summary.merge_all()
writer = tf.summary.FileWriter(BASE_LOGDIR + RUN)
writer.add_graph(sess.graph) 

# Train 
with sess.as_default():
    for cur_step in range(MAX_TRAIN_STEPS):
        batch = mnist.train.next_batch(BATCH_SIZE)
        if cur_step % output_steps == 0:
            train_kl_div, train_generation_loss = sess.run([kl_div, generation_loss], feed_dict={x: batch[0], y_true: batch[1]})
            #train_kl_div = sess.run(n_latent_sigma, feed_dict={x: batch[0], y_true: batch[1]})
            print('Step: ' + str(cur_step) + '\t\tTrain kld: ' + str(train_kl_div) + '\t\tTrain GenLoss: ' + str(train_generation_loss))
            # Calculate and write-out all summaries
            # Validate on batch from validation set
            val_batch = mnist.validation.next_batch(BATCH_SIZE)
            all_sums = sess.run(all_summaries, feed_dict={x: val_batch[0], y_true: val_batch[1]})
            writer.add_summary(all_sums, cur_step) 
        train_step.run(feed_dict={x: batch[0], y_true: batch[1]})


