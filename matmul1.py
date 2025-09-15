import random
import numpy as np
from time import time

# basic numpy matrix multiplication
# 实现了一个基本的矩阵乘法性能测试，并通过 OpenFaaS 事件处理函数进行触发。
def matmul(n):
    A = np.random.rand(n, n)   # 生成两个大小为 n x n 的随机矩阵 A 和 B。
    B = np.random.rand(n, n)

    start = time()               # 记录开始时间
    #print("记录开始时间")
    C = np.matmul(A, B)
    latency = time() - start
    return latency

# openfaas event handler function
def handle(event):
    input = [10, 100, 1000]
    n = random.randint(0, 2)
    result = matmul(input[n])  # 调用 matmul(n) 函数计算矩阵乘法，并返回计算的延迟时间。
    #print("返回计算的延迟时间")
    #print(result)
    return result
