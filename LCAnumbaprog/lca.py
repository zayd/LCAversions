import numpy as np
from numbapro import cuda
import numbapro.cudalib.cublas as cublas
from numba import *
@cuda.jit(argtypes=[f4[:,:],f4[:]])
def uinit(u,coeffs):
    n = u.shape[0]
    m = u.shape[1]
    i,j = cuda.grid(2)
    
    if i >= 1 and i < n - 1 and j >= 1 and j < m - 1:
        u[i,j] = coeffs[i]

@cuda.jit(argtypes=[f4[:,:],f4[:,:]])
def cinit(dictionary,c):
    n = dictionary.shape[0]
    m = dictionary.shape[1]
    i,j = cuda.grid(2)
    
    if i >= 1 and i < n - 1 and j >= 1 and j < n - 1 and (i or j):
        for k in xrange(m):
            c[i,j] += dictionary[i,k]*dictionary[j,k]

@cuda.jit(argtypes=[f4[:,:],f4[:,:],f4[:,:]])
def binit(dictionary,stimuli,b):
    n = stimuli.shape[0]
    m = dictionary.shape[0]
    k = dictionary.shape[1]
    i,j = cuda.grid(2)

    if i >= 1 and i < n - 1 and j >= 1 and j < m - 1:
        for r in xrange(k):
            b[i,j] += stimuli[i,r]*dictionary[j,r]

@cuda.jit(argtypes=[f4[:,:],f4[:,:],f4[:,:],f4[:,:],f4[:,:],f4,f4,f4,i4])
def iter(c,b,ci,u,s,eta,thresh,adapt,softThresh):
    n = u.shape[0]
    m = u.shape[1]
    i,j = cuda.grid(2)
    
    if i >= 1 and i < n - 1 and j >= 1 and j < m - 1:
        u[i,j] = eta*(b[i,j]-ci[i,j])+(1-eta)*u[i,j]
        if u[i,j] < thresh and u[i,j] > -thresh:
            s[i,j] = 0.
        elif softThresh == 1:
            if u[i,j] > 0.:
                s[i,j] = u[i,j]-thresh
            else:
                s[i,j] = u[i,j]+thresh
        else:
            s[i,j] = u[i,j]

def lca(dictionary,coeffs,stimuli,eta,lamb,nIter,softThresh,adapt):
#Initialize arrays
    u = np.zeros((stimuli.shape[0],dictionary.shape[0]))
    d_u = cuda.to_device(u)
    s = np.zeros((stimuli.shape[0],dictionary.shape[0]))
    d_s = cuda.to_device(s)
    b = np.zeros((stimuli.shape[0],dictionary.shape[0]))
    d_b = cuda.to_device(b)
    ci = np.zeros((stimuli.shape[0],dictionary.shape[0]))
    d_ci = cuda.to_device(ci)
    c = np.zeros((dictionary.shape[0],dictionary.shape[0]))
    d_c = cuda.to_device(c)
    
    #Move inputs to GPU
    d_dictionary = cuda.to_device(dictionary)
    d_coeffs = cuda.to_device(coeffs)
    d_stimuli = cuda.to_device(stimuli)

    blockdim = (32,32)
    griddim = (u.shape[0]/blockdim[0],u.shape[1]/blockdim[1])
    
    #Calculate c: overlap of basis functions with each other minus identity
    #should use symmetry to cut back on time, probably not important
    cinit(d_dictionary,d_c)
    binit(d_dictionary,d_stimuli,d_b)
    thresh = np.mean(np.absolute(d_b.copy_to_host()))
    #Update u[i] and s[i] for nIter time steps
    for kk in xrange(nIter):
        #Calculate ci: amount other neurons are stimulated times overlap with rest of basis
        ci = np.dot(s,c)
        d_ci = cuda.to_device(ci)
        iter[griddim,blockdim](d_c,d_b,d_ci,d_u,d_s,eta,thresh,adapt,softThresh)
        if thresh > lamb:
            thresh = adapt*thresh
    u = d_u.copy_to_host()
    s = d_s.copy_to_host()
    return (s,u,thresh)
