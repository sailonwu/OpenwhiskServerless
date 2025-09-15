from kubernetes import client, config
from kubernetes.client.rest import ApiException
import json

def convert_cpu(cpu_str):
    """将K8s CPU字符串转换为毫核(m)单位"""
    if not cpu_str:  # 处理空值
        return 0
    if cpu_str.endswith('n'):
        return int(cpu_str[:-1]) // 1_000_000
    elif cpu_str.endswith('u'):
        return int(cpu_str[:-1]) // 1_000
    elif cpu_str.endswith('m'):
        return int(cpu_str[:-1])
    else:
        return int(cpu_str) * 1000

def convert_memory(mem_str):
    """将K8s内存字符串转换为MiB单位"""
    if not mem_str:  # 处理空值
        return 0
    if mem_str.endswith('Ki'):
        return int(mem_str[:-2]) // 1024
    elif mem_str.endswith('Mi'):
        return int(mem_str[:-2])
    elif mem_str.endswith('Gi'):
        return int(mem_str[:-2]) * 1024
    else:
        return int(mem_str) // (1024**2)

# 配置加载
try:
    config.load_incluster_config()
except config.ConfigException:
    config.load_kube_config()

statefulset_name = 'owdev-invoker'
namespace = 'openwhisk'
scale_api = client.AppsV1Api()
metrics_api = client.CustomObjectsApi()

try:
    # 获取StatefulSet状态
    sts = scale_api.read_namespaced_stateful_set(name=statefulset_name, namespace=namespace)
    current_pods = sts.status.ready_replicas or 0
    print(f"[DEBUG] 当前就绪副本数: {current_pods}")

    # 获取容器资源限制（关键修改点）===========================================
    containers = sts.spec.template.spec.containers
    if not containers:
        raise RuntimeError(f"StatefulSet {statefulset_name} 未定义容器")
    
    resources = containers[0].resources or client.V1ResourceRequirements()
    limits = resources.limits or {}  # 从limits获取
    
    # 解析资源限制（必须定义limits才能计算繁忙程度）
    func_cpu = convert_cpu(limits.get('cpu', '0m'))
    func_mem = convert_memory(limits.get('memory', '0Mi'))
    
    # 检查是否设置资源限制
    if func_cpu <= 0 or func_mem <= 0:
        raise ValueError(f"容器未定义资源限制（limits），无法计算繁忙程度")
    # ======================================================================
    
    print(f"[DEBUG] 单Pod资源限制: CPU={func_cpu}m, 内存={func_mem}Mi")

    # 获取Pod指标
    pod_metrics = metrics_api.list_namespaced_custom_object(
        group="metrics.k8s.io",
        version="v1beta1",
        namespace=namespace,
        plural="pods"
    )
    all_pods = pod_metrics.get('items', [])

    # 筛选目标Pod
    my_pods = [
        pod['containers'][0]['usage']
        for pod in all_pods
        if pod['metadata']['name'].startswith(f"{statefulset_name}-")
    ]
    print(f"\n[INFO] 找到 {len(my_pods)} 个相关Pod")

    # 计算资源使用率（基于limits）============================================
    cpu_total = 0
    mem_total = 0
    for usage in my_pods:
        try:
            # 当前实际使用量
            current_cpu = convert_cpu(usage['cpu'])
            current_mem = convert_memory(usage['memory'])
            
            cpu_total += current_cpu
            mem_total += current_mem
            
            # 调试输出单个Pod使用率
            cpu_percent = current_cpu / func_cpu if func_cpu >0 else 0
            mem_percent = current_mem / func_mem if func_mem >0 else 0
            print(f"Pod: {pod['metadata']['name']} CPU使用率: {cpu_percent:.2%}, 内存使用率: {mem_percent:.2%}")
        except (KeyError, ValueError) as e:
            print(f"[WARNING] 指标解析失败: {str(e)}")

    avg_cpu_percent = (cpu_total / len(my_pods)) / func_cpu if my_pods else 0
    avg_mem_percent = (mem_total / len(my_pods)) / func_mem if my_pods else 0
    # ======================================================================

    # 扩缩容决策（基于资源限制的阈值）==========================================
    print("\n[决策分析]")
    print(f"平均CPU使用率（相对于limits）: {avg_cpu_percent:.2%}")
    print(f"平均内存使用率（相对于limits）: {avg_mem_percent:.2%}")
    
    # 任一资源超过80%则扩容，所有资源低于30%则缩容
    if avg_cpu_percent > 0.8 or avg_mem_percent > 0.8:
        scale_value = current_pods + 1
        print("触发扩容条件：资源使用率 >80%")
    elif avg_cpu_percent < 0.3 and avg_mem_percent < 0.3:
        scale_value = max(current_pods - 1, 1)
        print("触发缩容条件：资源使用率 <30%")
    else:
        scale_value = current_pods
        print("保持当前副本数")
    # ======================================================================

    # 执行扩缩容
    body = {'spec': {'replicas': scale_value}}
    response = scale_api.patch_namespaced_stateful_set_scale(
        name=statefulset_name,
        namespace=namespace,
        body=body
    )
    print(f"\n[INFO] 扩缩容成功! 新副本数: {response.spec.replicas}")

except ApiException as e:
    error_msg = f"[ERROR] API错误: {e.reason} (状态码: {e.status})"
    if e.body:
        error_details = e.body.get('message', '')
        error_msg += f"\n详情: {error_details}"
    print(error_msg)
except Exception as e:
    print(f"[CRITICAL] 错误: {str(e)}")
