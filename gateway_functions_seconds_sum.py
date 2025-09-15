from datetime import datetime
import time as time
import math
import json as json
import numpy as np
#import gymnasium as gym   #定义强化学习环境的标准化接口。
#from gymnasium import spaces
#import tensorflow as tf

from kubernetes import client, config
from prometheus_api_client import PrometheusConnect
prom = PrometheusConnect(url="http://192.168.80.134:32018", disable_ssl=True)

query1 = "(rate(gateway_functions_seconds_sum[30s]) / \
                rate(gateway_functions_seconds_count[30s]))"
query_all = 'gateway_functions_seconds_sum'
data0 = prom.custom_query(query_all)
print(data0)
data1 = prom.custom_query(query=query1)
print(data1)
