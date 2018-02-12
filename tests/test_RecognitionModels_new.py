# Copyright 2018 Daniel Hernandez Diaz, Columbia University
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
#
# ==============================================================================
from __future__ import print_function
from __future__ import division

import numpy as np

import tensorflow as tf

from LatEvModels_new import LocallyLinearEvolution
from ObservationModels_new import PoissonObs
from RecognitionModels_new import SmoothingNLDSTimeSeries


class SmoothingNLDSTimeSeries(tf.test.TestCase):
    """
    """
    yDim = 10
    xDim = 2
    
    rndints = np.random.randint(1000, size=100).tolist()
        
    graph = tf.Graph()
    with graph.as_default():
        X = tf.placeholder(tf.float64, [None, None, xDim], 'X')
        Y = tf.placeholder(tf.float64, [None, None, yDim], 'Y')
        
        mrec = SmoothingNLDSTimeSeries(yDim, xDim, Y, X)
        lm = mrec.get_lat_ev_model()
        mgen = PoissonObs(yDim, xDim, Y, X, lm)
        
        # Let us first generate some data that we may use
        with tf.Session() as sess:
            Ydata, Xdata = mgen.sample_XY(sess, with_inflow=True, Nsamps=3, NTbins=4)
#             print(Ydata, Xdata)
    
    
    def test_simple(self):
        with tf.Session(graph=self.graph) as sess:
            sess.run(tf.global_variables_initializer())
            Mu = sess.run(self.mrec.Mu_NxTxd, feed_dict={'Y:0' : self.Ydata})            
            LambdaMu = sess.run(self.mrec.LambdaMu_NxTxd, feed_dict={'Y:0' : self.Ydata})
            print('Mu:', Mu)
            print('LambdaMu:', LambdaMu)
             
    def test_postX(self):
        with tf.Session(graph=self.graph) as sess:
            sess.run(tf.global_variables_initializer())
            postX = sess.run(self.mrec.postX, feed_dict={'Y:0' : self.Ydata,
                                                         'X:0' : self.Xdata})
#             print(postX, postX.shape)
            TheChol = sess.run(self.mrec.TheChol_2xNxTxdxd, feed_dict={'Y:0' : self.Ydata,
                                                           'X:0' : self.Xdata})
#             AA = sess.run(self.mrec.AA_NxTxdxd, feed_dict={'Y:0' : self.Ydata,
#                                                            'X:0' : self.Xdata})
#             print(TheChol[0].shape)
#             print(TheChol[0])

    def test_Entropy(self):
        with tf.Session(graph=self.graph) as sess:
            sess.run(tf.global_variables_initializer())
            Entropy = sess.run(self.mrec.Entropy, feed_dict={'Y:0' : self.Ydata,
                                                             'X:0' : self.Xdata})
#             print('Entropy', Entropy)

    def test_Entropy_winput(self):
        rndint = self.rndints.pop()
        with self.graph.as_default():
            XInput = tf.placeholder(dtype=tf.float64, shape=[None, None, self.xDim], 
                                    name='Xinput_1')
            Ewinput = self.mrec.compute_Entropy(XInput) 
        with tf.Session(graph=self.graph) as sess:
            np.random.seed(rndint)
            sess.run(tf.global_variables_initializer())
            Ydata, Xdata = self.mgen.sample_XY(sess, init_variables=False,
                                               with_inflow=True)
            Ewinput = sess.run(Ewinput, feed_dict={'Xinput_1:0' : Xdata,
                                                   'Y:0' : Ydata})
#             print('E:', Ewinput)

#     def test_sample_postX(self):
#         with self.graph.as_default():
#             samps = self.mrec.sample_postX()
#         with tf.Session(graph=self.graph) as sess:
#             sess.run(tf.global_variables_initializer())
#             samps_nmric = sess.run(samps, feed_dict={'Y:0' : self.Ydata,
#                                                      'X:0' : self.Xdata})
#             print('Samps numeric', samps_nmric)
        
    
    
    
if __name__ == '__main__':
    tf.test.main()
