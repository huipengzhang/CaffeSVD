#coding=utf-8
import caffe
from caffe import layers as L, params as P, to_proto
from caffe.proto import caffe_pb2
import lmdb
import numpy as np
from numpy import linalg as la
import matplotlib.pyplot as plt 
from base import *

CAFFE_HOME = "/opt/caffe/"

deploy = "./proto/cifar10_quick.prototxt"
SVD_R = 8
deploySVD = GetSVDProto(SVD_R)#"./proto/cifar10_SVD%d.prototxt" % SVD_R
caffe_model = CAFFE_HOME + "/examples/cifar10/cifar10_quick_iter_5000.caffemodel.h5" 
train_db = CAFFE_HOME + "examples/cifar10/cifar10_train_lmdb"
test_db = CAFFE_HOME + "examples/cifar10/cifar10_test_lmdb"
mean_proto = CAFFE_HOME + "examples/cifar10/mean.binaryproto"
mean_npy = "./mean.npy"
mean_pic = np.load(mean_npy)

def read_db(db_name):
    lmdb_env = lmdb.open(db_name)
    lmdb_txn = lmdb_env.begin()
    lmdb_cursor = lmdb_txn.cursor()
    datum = caffe.proto.caffe_pb2.Datum()

    X = []
    y = []
    for key, value in lmdb_cursor:
        datum.ParseFromString(value)
        label = datum.label
        data = caffe.io.datum_to_array(datum)
        #data = data.swapaxes(0, 2).swapaxes(0, 1)
        X.append(data)
        y.append(label)
        #plt.imshow(data)
        #plt.show()
    return X, np.array(y)

testX, testy = read_db(test_db)

# Load model and network
net = caffe.Net(deploy, caffe_model, caffe.TEST) 
netSVD = caffe.Net(deploySVD, caffe_model, caffe.TEST)

for layer_name, param in net.params.items():
    # 0 is weight, 1 is biase
    print (layer_name, param[0].data.shape)

print ("SVD NET:")
for layer_name, param in netSVD.params.items():
    # 0 is weight, 1 is biase
    print (layer_name, param[0].data.shape)

print (type(net.params))
print (net.params.keys())
print ("layer ip2:")
print ("WEIGHT:")
print (net.params["ip2"][0].data.shape)
print ("BIASES:")
print (net.params["ip2"][1].data.shape)


data, label = L.Data(source = test_db, backend = P.Data.LMDB, batch_size = 100, ntop = 2, mean_file = mean_proto)

# SVD
print ("SVD")
u, sigma, vt = la.svd(net.params["ip2"][0].data)
U = u[:, :SVD_R]
S = np.diag(sigma[:SVD_R])
VT = vt[:SVD_R, :]

# y = Wx + b
# y = U * S * VT * x + b

np.copyto(netSVD.params["ipVT"][0].data, VT)
np.copyto(netSVD.params["ipS"][0].data, S)
np.copyto(netSVD.params["ipU"][0].data, U)
np.copyto(netSVD.params["ipU"][1].data, net.params["ip2"][1].data)


n = len(testX)
pre = np.zeros(testy.shape)
print ("N = %d" % n)
for i in range(n):
    net.blobs["data"].data[...] = testX[i] - mean_pic 
    net.forward()
    prob = net.blobs["prob"].data
    pre[i] = prob.argmax() 
    print ("%d / %d" % (i + 1, n))
right = np.sum(pre == testy) 
print ("Accuracy: %f" % (right * 1.0 / n))

np.save("net_normal.npy", pre)