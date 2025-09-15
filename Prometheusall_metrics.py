from prometheus_api_client import PrometheusConnect

prom = PrometheusConnect(url="http://192.168.80.134:32018", disable_ssl=True)

# 获取 Prometheus 里的所有可用指标
all_metrics = prom.all_metrics()

# 打印所有指标，看看 `gateway_functions_seconds_sum` 是否存在
print("Available Metrics:")
for metric in all_metrics:
    print(metric)

