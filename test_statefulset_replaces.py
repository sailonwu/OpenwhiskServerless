from kubernetes import client, config
from kubernetes.client.rest import ApiException

# 加载K8s配置（自动适配集群内/外环境）
config.load_config()  

statefulset_name = 'owdev-invoker'
namespace = 'openwhisk'
scale_api = client.AppsV1Api()

try:
    # 1. 获取当前StatefulSet状态
    sts = scale_api.read_namespaced_stateful_set(
        name=statefulset_name,
        namespace=namespace
    )
    current_pods = sts.status.ready_replicas or 0
    print(f"当前就绪副本数: {current_pods}")

    # 2. 计算目标副本数（示例逻辑：当前副本数+1）
    scale_value = current_pods - 1
    body = {'spec': {'replicas': scale_value}}

    # 3. 执行扩缩容操作
    response = scale_api.patch_namespaced_stateful_set_scale(
        name=statefulset_name,
        namespace=namespace,
        body=body
    )
    print(f"扩缩容成功! 新副本数: {response.spec.replicas}")

except ApiException as e:
    # 统一处理K8s API错误（如权限不足、资源不存在等）
    error_msg = f"K8s API操作失败: {e.reason} (状态码: {e.status})"
    if e.body:
        error_details = e.body.get('message', '')
        error_msg += f"\n详情: {error_details}"
    print(error_msg)
    # 根据业务逻辑设置默认值或抛出异常
    current_pods = 0  
