#vi test_pod_metrics1.py
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import json

# 自动选择集群内/外配置加载
try:
    config.load_incluster_config()  # 集群内运行
except config.ConfigException:
    config.load_kube_config()       # 本地开发环境

statefulset_name = 'owdev-invoker'
namespace = 'openwhisk'
scale_api = client.AppsV1Api()
metrics_api = client.CustomObjectsApi()  # 新增Metrics API客户端

try:
    # 1. 获取StatefulSet当前状态
    sts = scale_api.read_namespaced_stateful_set(
        name=statefulset_name,
        namespace=namespace
    )
    current_pods = sts.status.ready_replicas or 0
    print(f"[DEBUG] 当前就绪副本数: {current_pods}")

    # 2. 获取Pod资源指标（新增部分）=============================================
    print("\n[DEBUG] 开始获取Pod指标...")
    pod_metrics = metrics_api.list_namespaced_custom_object(
        group="metrics.k8s.io",
        version="v1beta1",
        namespace=namespace,
        plural="pods"
    )
    print("\n[INFO] Pod资源使用摘要:")
    all_pods = pod_metrics.get('items', [])

    # 调试：打印所有Pod的标签（确认标签键是否正确）
    print("\n[DEBUG] 所有Pod的标签:")

    for pod in all_pods:
        labels = pod['metadata'].get('labels', {})
        print(f"Pod: {pod['metadata']['name']}")
        #print(f"  标签: {json.dumps(labels, indent=4, ensure_ascii=False)}")

    # 筛选目标Pod（关键修改部分）===============================================
    try:
        my_pods = [
            pod['containers'][0]['usage']
            for pod in all_pods
            if pod['metadata']['labels'].get('name') == statefulset_name  # 注意：这里需要确认实际标签键
        ]

        print(f"\n[INFO] 找到 {len(my_pods)} 个匹配标签 name={statefulset_name} 的Pod")
        print("筛选目标 my_pods",my_pods)
        cpu = 0
        mem = 0
        for pods in my_pods:
            # 获取 CPU 和内存使用情况
            c = pods['cpu']
            m = pods['memory']
            try:
                # 将 CPU 使用量转换为毫核 (m)
                # converting everything in to millicores (m) 1 vCPU = 1000m
                if c.endswith('n'):
                    cpu += (round(int(c.split('n')[0])/1e6, 4))
                elif c.endswith('u'):
                    cpu += (round(int(c.split('u')[0])/1e3, 4))
                elif c.endswith('m'):
                    cpu += (round(int(c.split('m')[0]), 4))
                else:
                        cpu += 0
            except Exception as e:
                cpu += 0
            try:    
                # converting everything into Gi
                # 将内存使用量转换为 Gi
                if m.endswith('Ki'):
                    mem += (round(int(m.split('Ki')[0])/(1024*1024), 4))
                elif m.endswith('Mi'):
                    mem += (round(int(m.split('Mi')[0])/1024, 4))
                elif m.endswith('Gi'):
                    mem += (round(int(m.split('Gi')[0]), 4))
                else:
                    mem += 0
            except Exception as e:
                mem += 0
        # 计算平均 CPU 和内存使用率
        func_cpu = 150
        func_mem = round((256/1024), 2)
        avg_cpu = round((cpu/len(my_pods))/func_cpu, 4)
        avg_mem = round((mem/len(my_pods))/func_mem, 4)
        print("平均 CPU 和内存使用率:",avg_cpu,avg_mem)

    except KeyError as e:
        print(f"[ERROR] 标签不存在或数据结构异常: {str(e)}")
        my_pods = []
        avg_cpu = 0
        avg_mem = 0
            
    # 打印原始JSON响应（调试用）
    #print("\n[DEBUG] 原始指标响应结构:")
    #print(json.dumps(pod_metrics, indent=2, ensure_ascii=False))

    # 解析并打印关键指标
    #print("\n[INFO] 所有Pod资源使用摘要:")
    #for item in pod_metrics.get('items', []):
    #    pod_name = item['metadata']['name']
    #    cpu_usage = item['containers'][0]['usage']['cpu']
    #    mem_usage = item['containers'][0]['usage']['memory']
    #    print(f" - Pod: {pod_name}")
    #    print(f"   CPU: {cpu_usage}, 内存: {mem_usage}")
    # ========================================================================

    # 3. 执行扩缩容（示例：当前副本数+1）
    scale_value = 1    #current_pods + 1

    body = {'spec': {'replicas': scale_value}}

    response = scale_api.patch_namespaced_stateful_set_scale(
        name=statefulset_name,
        namespace=namespace,
        body=body
    )
    print(f"\n[INFO] 扩缩容成功! 新副本数: {response.spec.replicas}")

except ApiException as e:
    error_msg = f"[ERROR] K8s API错误: {e.reason} (状态码: {e.status})"
    if e.body:
        error_details = e.body.get('message', '')
        error_msg += f"\n详情: {error_details}"
    print(error_msg)
    current_pods = 0
except Exception as e:
    print(f"[CRITICAL] 未知错误: {str(e)}")

