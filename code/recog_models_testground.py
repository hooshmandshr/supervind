# Copyright 2017 Daniel Hernandez Diaz, Columbia University
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

from utils import variable_in_cpu, blk_tridiag_chol, blk_chol_inv

def FullLayer(Input, nodes, input_dim=None, nl='softplus'):
    nl_dict = {'softplus' : tf.nn.softplus, 'linear' : tf.identity}
    nonlinearity = nl_dict[nl]
    
    weights_full1 = variable_in_cpu('weights', [input_dim, nodes], 
                          initializer=tf.random_normal_initializer())
    biases_full1 = variable_in_cpu('biases', [nodes], 
                             initializer=tf.constant_initializer())
    full = nonlinearity(tf.matmul(Input, weights_full1) + biases_full1,
                          name='full1')
    return full


class SmoothingNLDSTimeSeries():
    """
    """
    def __init__(self, yDim, xDim, Y, X, lat_ev_model):
        """
        """
        self.yDim = yDim
        self.xDim = xDim
        self.Y = Y
        self.X = X
        self.lat_ev_model = lat_ev_model
        
        self.Nsamps = Nsamps = tf.shape(self.Y)[0]
        self.NTbins = NTbins = tf.shape(self.Y)[1]
        
        rec_nodes = 60
        Y_input_NTxD = tf.reshape(Y, [Nsamps*NTbins, yDim])
        with tf.variable_scope("Recognition_Network_Mu"):
            with tf.variable_scope('full1'):
                full1 = FullLayer(Y_input_NTxD, rec_nodes, yDim, 'softplus')
            with tf.variable_scope('full2'):
                full2 = FullLayer(full1, rec_nodes, rec_nodes, 'softplus')
            with tf.variable_scope('full3'):
                self.Mu_NTxd = FullLayer(full2, xDim, rec_nodes, 'linear')
        
        with tf.variable_scope("Recognition_Network_Lambda"):
            with tf.variable_scope('full1'):
                full1 = FullLayer(Y_input_NTxD, rec_nodes, yDim, 'softplus')
            with tf.variable_scope('full2'):
                full2 = FullLayer(full1, rec_nodes, rec_nodes, 'softplus')
            with tf.variable_scope('full3'):
                full3 = FullLayer(full2, xDim**2, rec_nodes, 'linear')
        LambdaChol_NTxdxd = tf.reshape(full3, [Nsamps*NTbins, xDim, xDim])
        Lambda_NTxdxd = tf.matmul(LambdaChol_NTxdxd, LambdaChol_NTxdxd,
                                 transpose_b=True)
        self.Lambda_NxTxdxd = tf.reshape(Lambda_NTxdxd, [Nsamps, NTbins, xDim, xDim])
        
        LambdaMu_NTxd = tf.squeeze(tf.matmul(Lambda_NTxdxd, 
                                tf.expand_dims(self.Mu_NTxd, axis=2)), axis=2)
        self.LambdaMu_NxTxd = tf.reshape(LambdaMu_NTxd, [Nsamps, NTbins, xDim])
        
        # ****************************
        QInv_dxd = self.lat_ev_model.QInv_dxd
        Q0Inv_dxd = self.lat_ev_model.Q0Inv_dxd
        totalA_NTm1xdxd = tf.reshape(self.lat_ev_model.totalA_NxTxdxd[:,:-1,:,:],
                                     [Nsamps*(NTbins-1), xDim, xDim])
        QInvs_NTm1xdxd = tf.tile(tf.expand_dims(QInv_dxd, axis=0),
                                   [Nsamps*(NTbins-1), 1, 1])
#         self.QInv = self.lat_ev_model.get_QInv()
#         self.Q0Inv = self.lat_ev_model.get_Q0Inv()
#         self.totalA = T.reshape(self.lat_ev_model.get_totalA(), 
#                                 [self.Nsamps*(self.Tbins-1), self.xDim, self.xDim])   # implicit symbolic dependence on self.gen_model.X
#         self.QQInv = T.tile(self.QInv, [self.Nsamps*(self.Tbins-1), 1, 1])
        
        
        # Computes the block diagonal matrix:
        #     Qt^-1 = diag{Q0^-1, Q^-1, ..., Q^-1}
        QInvs_Tm2xdxd = tf.tile(tf.expand_dims(QInv_dxd, axis=0),
                                   [(NTbins-2), 1, 1])
        Q0Inv_1xdxd = tf.expand_dims(Q0Inv_dxd, axis=0)
        Q0QInv_Tm1xdxd = tf.concat([Q0Inv_1xdxd, QInvs_Tm2xdxd], axis=0)
        QInvsTot_NTm1xdxd = tf.tile(Q0QInv_Tm1xdxd, [Nsamps, 1, 1])
#         QInv = T.tile(self.QInv, [self.Tbins-2, 1, 1])
#         Q0Inv = T.reshape(self.Q0Inv, [1, self.xDim, self.xDim])
#         Q0QInv = T.concatenate([Q0Inv, QInv], axis=0)
#         self.QInvTot = T.tile(Q0QInv, [self.Nsamps, 1, 1])

        # The diagonal blocks of Omega(z) up to T-1:
        #     Omega(z)_ii = A(z)^T*Qq^{-1}*A(z) + Qt^{-1},     for i in {1,...,T-1 }
        AQInvsA_NTm1xdxd = ( tf.matmul(totalA_NTm1xdxd, 
                                     tf.matmul(QInvs_NTm1xdxd, totalA_NTm1xdxd),
                                     transpose_a=True) + QInvsTot_NTm1xdxd )
        AQInvsA_NxTm1xdxd = tf.reshape(AQInvsA_NTm1xdxd, [Nsamps, NTbins-1, xDim, xDim])                                     
#         self.AQInvA = T.batched_dot(self.totalA.dimshuffle(0, 2, 1), 
#                             T.batched_dot(self.QQInv, self.totalA)) + self.QInvTot
#         self.AQInvA = self.AQInvA.reshape([self.Nsamps, self.Tbins-1, self.xDim, self.xDim])
        
        # The off-diagonal blocks of Omega(z):
        #     Omega(z)_{i,i+1} = A(z)^T*Q^-1,     for i in {1,..., T-2} 
        AQInvs_NTm1xdxd = -tf.matmul(totalA_NTm1xdxd, QInvs_NTm1xdxd,
                                     transpose_a=True)
        AQInvs_NTm1xdxd = tf.reshape(AQInvs_NTm1xdxd, [Nsamps, NTbins-1, xDim, xDim])
#         self.AQInv = -T.batched_dot(self.totalA.dimshuffle(0, 2, 1), self.QQInv)
#         self.AQInv = self.AQInv.reshape([self.Nsamps, self.Tbins-1, self.xDim, self.xDim])
        
        # Tile in the last block Omega_TT. 
        # This one does not depend on A. There is no latent evolution beyond T.
        QInvs_Nx1xdxd = tf.tile(tf.reshape(QInv_dxd, shape=[1, 1, 2, 2]), 
                                [Nsamps, 1, 1, 1])
#         QInvRep = T.tile(self.QInv, [self.Nsamps, 1, 1, 1])
        AQInvsAQInv_NxTxdxd = tf.concat([AQInvsA_NxTm1xdxd, QInvs_Nx1xdxd], axis=1)
#         self.AQInvAPlusQ = T.concatenate([self.AQInvA, QInvRep], axis=1)
        
        # Add in the covariance coming from the observations
        self.AA_NxTxdxd = self.Lambda_NxTxdxd + AQInvsAQInv_NxTxdxd
        self.BB_NxTm1xdxd = tf.reshape(AQInvs_NTm1xdxd, [Nsamps, NTbins-1, xDim, xDim])
#         self.AA = self.Lambda + self.AQInvAPlusQ    # NxTxdxd
#         self.BB = self.AQInv    # NxT-1xdxd
        
        
        # Computation of the variational posterior mean
        aux_fn1 = lambda _, seqs : blk_tridiag_chol(seqs[0], seqs[1])
        self.TheChol = tf.scan(fn=aux_fn1, elems=[self.AA_NxTxdxd, self.BB_NxTm1xdxd])
#         self.TheChol, _ = theano.scan(lambda A, B : blk_tridiag_chol(A, B),
#                                        sequences = (self.AA, self.BB))
        def postX_from_chol(tc1, tc2, lm):
            """
            postX = (Lambda1 + Lambda2)^{-1}.Lambda1.Mu
            """
            return blk_chol_inv(tc1, tc2, blk_chol_inv(tc1, tc2, lm), 
                                lower=False, transpose=True)
#         self.postX, _ = theano.scan(lambda tc1, tc2, lm : postX_from_chol(tc1, tc2, lm), 
#                         sequences=(self.TheChol[0], self.TheChol[1], self.LambdaMu))
        aux_fn2 = lambda _, seqs : postX_from_chol(seqs[0], seqs[1], seqs[2])
        self.postX = tf.scan(fn=aux_fn2, 
                    elems=[self.TheChol[0], self.TheChol[1], self.LambdaMu_NxTxd],
                    initializer=tf.zeros_like(self.LambdaMu_NxTxd[0], dtype=tf.float64) )
        

#         Xflat = self.X.reshape([self.Nsamps*self.Tbins, self.xDim])
#         Xflat01 = self.X[:,:-1,:].reshape([self.Nsamps*(self.Tbins-1), self.xDim])
#         Xflat10 = self.X[:,1:,:].reshape([self.Nsamps*(self.Tbins-1), self.xDim])

        #=== PROCEED TO THE METHODS OF THE CLASS FOR NOW IF YOU ARE A USER ===#
        
        def compute_grad_term():
            """
            TODO: This implementatio is way too slow. THIS IS THE MOST IMPORTANT
            THING TO BE DONE
            """
            self.grad_AA_NTxdxdxd = covariance_time_series_grad(self.AA, self.Y, self.X, self.xDim)
            self.grad_BB_NTm1xdxdxd = covariance_time_series_grad(self.BB, self.Y, self.X, 
                                                              self.xDim, remove_from_tail=1)
#             gradA_func = theano.function([self.X, self.Y], self.grad_AA_NTxdxdxd)
#             assert False
        
            test_AA = T.batched_tensordot(Xflat, 
                    T.batched_tensordot(self.grad_AA_NTxdxdxd, Xflat, axes=[[3],[1]]),
                    axes=[[1],[2]]).reshape([self.Nsamps, self.Tbins, self.xDim])
    #         test_AA_func = theano.function([self.X, self.Y], test_AA)
            test_BB = T.batched_tensordot(Xflat01, 
                    T.batched_tensordot(self.grad_BB_NTm1xdxdxd, Xflat10, axes=[[3],[1]]),
                    axes=[[1],[2]])
            test_BB = T.concatenate([test_BB.reshape([self.Nsamps, self.Tbins-1, self.xDim]), 
                                     T.zeros([self.Nsamps, 1, self.xDim])], axis=1)
            final_term = -0.5*test_AA - test_BB
            return final_term
    #         test_BB = T.batched_dot(a, b)
    #         print 'Doing the gradients'
    #         grad_AA = covariance_time_series_grad(self.AA)
    #         grad_BB_func = theano.function([self.X, self.Y], self.grad_BB_NxTm1xdxdxd)
    
    #         test_BB_func = theano.function([self.X, self.Y], test_BB)
    #         sampleY = np.random.rand(2, 3, 10)
    #         sampleX = np.random.rand(2, 3, 2)
    #         print 'Finished gradients'
    #         print 'GradBB:', grad_BB_func(sampleX, sampleY)
    #         sampleY = np.random.rand(2, 3, 10)
    #         sampleX = np.random.rand(2, 3, 2)        
    #         print 'Eval gradients:', test_AA_func(sampleX, sampleY)
    #         print 'Eval gradients:', test_BB_func(sampleX, sampleY)
    #         assert False
        
        # Compute Cholesky decomposition for all samples.
        # A is Txdxd, B is T-1xdxd
#         self.TrueSol = self.LambdaMu + final_term
#         
# #         sampleY = np.random.rand(2, 3, 10)
# #         sampleX = np.random.rand(2, 3, 2)        
# #         print 'final', test_AA.eval({self.Y : sampleY, self.X : sampleX})
#         self.Xsol, _ =  theano.scan(lambda tc1, tc2, lm : postX_from_chol(tc1, tc2, lm), 
#                                     sequences=(self.TheChol[0], self.TheChol[1], self.TrueSol))
        
        # Determinant of the Cholesky factor is the product of the diagonal elements of the block-diagonal.     
        
        
        
        
        
        