# OpenwhiskServerless
1. 在 Kubernetes 环境下部署 OpenWhisk 服务
   1> 搭建 Kubernetes 集群
   2> 安装 Docker
   3> 安装 Kubernetes 组件
kubectl get nodes
NAME           STATUS   ROLES    AGE     VERSION
k8s-master     Ready    master   4h15m   v1.19.3
k8s-worker-1   Ready    <none>   4h14m   v1.19.3

2. 搭建 OpenWhisk 服务
  1>. 安装 Helm
   2> 配置 Dynamic Storage Provisioning
   3> 部署 OpenWhisk
   4>. 测试
   在 Master 节点上，我们测试函数的创建与调用。
    
    新建文件hello.js, 内容如下：
    
    function main(params) {
    var name;
    if(params.name == undefined)
        name = 'World';
    else
        name = params.name;
     return {
         payload:'Hello, ' + name + '!'};
    }
    执行以下命令，创建函数。我们创建了一个名为hellojs的函数。
    
    wsk action create -i hellojs hello.js
    执行以下命令，调用函数。
    
    wsk action invoke -i hellojs --result --param name Zinuo
3. k8s部署Prometheus+Grafana
           部署Prometheus
        创建命名空间
        
        操作节点[master1]
        
        kubectl create namespace prometheus-work
        1.
        部署Prometheus deploy
        
        操作节点[master1]
        
        cat >prome_deploy.yml<< "EOF"
        apiVersion: apps/v1
        kind: Deployment
        metadata:
          name: prometheus
          namespace: prometheus-work
          labels:
            app: prometheus
        spec:
          selector:
            matchLabels:
              app: prometheus
          template:
            metadata:
              labels:
                app: prometheus
            spec:
              securityContext:                                   #指定运行的用户为root
                runAsUser: 0
              serviceAccountName: prometheus
              containers:
              - image: prom/prometheus:v2.30.2
                name: prometheus
                args:
                - "--config.file=/etc/prometheus/prometheus.yml" #通过volume挂载prometheus.yml
                - "--storage.tsdb.path=/prometheus"              #通过vlolume挂载目录/prometheus
                - "--storage.tsdb.retention.time=24h"
                - "--web.enable-admin-api"                       #控制对admin HTTP API的访问
                - "--web.enable-lifecycle"                       #支持热更新，直接执行localhost:9090/-/reload立即生效
                ports:
                - containerPort: 9090
                  name: http
                volumeMounts:
                - mountPath: "/etc/prometheus"
                  name: config-volume
                - mountPath: "/prometheus"
                  name: data
                resources:
                  requests:
                    cpu: 100m
                    memory: 512Mi
                  limits:
                    cpu: 100m
                    memory: 512Mi
              volumes:
              - name: data
                persistentVolumeClaim:
                  claimName: prometheus-data  #本地存储
              - name: config-volume
                configMap:
                  name: prometheus-config     #定义的prometeus.yaml
        
        EOF
        kubectl apply -f prome_deploy.yml
        
        部署Prometheus service
        
        操作节点[master1]
        
        cat> prome_svc.yml<< "EOF"
        apiVersion: v1
        kind: Service
        metadata:
          name: prometheus
          namespace: prometheus-work
          labels:
            app: prometheus
        spec:
          selector:
            app: prometheus
          type: NodePort
          ports:
            - name: web
              port: 9090
              targetPort: http
        EOF
        kubectl apply -f prome_svc.yml
        
        部署configmap
        
        操作节点[master1]
        
        cat > prome_cfg.yml << "EOF"
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: prometheus-config
          namespace: prometheus-work
        data:
          prometheus.yml: |
            global:
              scrape_interval: 15s
              scrape_timeout: 15s
            scrape_configs:
            - job_name: 'prometheus'
              static_configs:
              - targets: ['localhost:9090']
        
        EOF
         kubectl apply -f prome_cfg.yml
        
        部署PV，PVC
        
        操作节点[node01]
        
        #在node01节点上执行
        mkdir /data/k8s/prometheus -p
        1.
        2.
        操作节点[master1]
        
        cat > prome_pvc.yml << "EOF"
        apiVersion: v1
        kind: PersistentVolume
        metadata:
          name: prometheus-local
          labels:
            app: prometheus
        spec:
          accessModes:
          - ReadWriteOnce
          capacity:
            storage: 5Gi
          storageClassName: local-storage
          local:
            path: /data/k8s/prometheus  #在node01节点创建此目录
          nodeAffinity:
            required:
              nodeSelectorTerms:
              - matchExpressions:
                - key: kubernetes.io/hostname
                  operator: In
                  values:
                  - node01   #指定运行在node节点
          persistentVolumeReclaimPolicy: Retain
        ---
        apiVersion: v1
        kind: PersistentVolumeClaim
        metadata:
          name: prometheus-data
          namespace: prometheus-work
        spec:
          selector:
            matchLabels:
              app: prometheus
          accessModes:
          - ReadWriteOnce
          resources:
            requests:
              storage: 5Gi
          storageClassName: local-storage
        
        EOF
        kubectl apply -f prome_pvc.yml
        
        配置rabc
        
        操作节点[master1]
        
        cat > prome_rabc.yml << "EOF"
        apiVersion: v1
        kind: ServiceAccount
        metadata:
          name: prometheus
          namespace: prometheus-work
        ---
        apiVersion: /v1
        kind: ClusterRole        #创建一个clusterrole
        metadata:
          name: prometheus
        rules:
        - apiGroups:
          - ""
          resources:
          - nodes
          - services
          - endpoints
          - pods
          - nodes/proxy
          verbs:
          - get
          - list
          - watch
        - apiGroups:
          - "extensions"
          resources:
            - ingresses
          verbs:
          - get
          - list
          - watch
        - apiGroups:
          - ""
          resources:
          - configmaps
          - nodes/metrics
          verbs:
          - get
        - nonResourceURLs:
          - /metrics
          verbs:
          - get
        ---
        apiVersion: /v1
        kind: ClusterRoleBinding
        metadata:
          name: prometheus
        roleRef:
          apiGroup: 
          kind: ClusterRole
          name: prometheus
        subjects:
        - kind: ServiceAccount
          name: prometheus
          namespace: prometheus-work
        
        EOF
        kubectl apply -f prome_rabc.yml
        
        查看部署的Prometheus服务
        
        操作节点[master1]
        
        [root@master1 ~]# kubectl get pod,svc,configmap,sa -n prometheus-work
        NAME                             READY   STATUS    RESTARTS   AGE
        pod/prometheus-db4b5c549-6gb7d   1/1     Running   0          4m39s
        
        NAME                 TYPE       CLUSTER-IP      EXTERNAL-IP   PORT(S)          AGE
        service/prometheus   NodePort   10.103.99.200   <none>        9090:30512/TCP   15m    #注意这个30512是后面要访问的端口
        
        NAME                          DATA   AGE
        configmap/kube-root-ca.crt    1      17m
        configmap/prometheus-config   1      14m
        
        NAME                        SECRETS   AGE
        serviceaccount/default      0         17m
        serviceaccount/prometheus   0         12m
        
        在浏览器访问Prometheus 访问地址是node节点IP加上service的nodeport端口
        192.168.48.104:30512
        部署grafana
        部署deployment
        
        cat >grafana.yml <<"EOF"
        kind: Deployment
        apiVersion: apps/v1
        metadata:
          labels:
            app: grafana
          name: grafana
          namespace: prometheus-work
        spec:
          replicas: 1
          revisionHistoryLimit: 10
          selector:
            matchLabels:
              app: grafana
          template:
            metadata:
              labels:
                app: grafana
            spec:
              securityContext:
                runAsNonRoot: true
                runAsUser: 10555
                fsGroup: 10555
              containers:
                - name: grafana
                  image: grafana/grafana:8.4.4
                  imagePullPolicy: IfNotPresent
                  env:
                    - name: GF_AUTH_BASIC_ENABLED
                      value: "true"
                    - name: GF_AUTH_ANONYMOUS_ENABLED
                      value: "false"
                  readinessProbe:
                    httpGet:
                      path: /login
                      port: 3000
                  volumeMounts:
                    - mountPath: /var/lib/grafana
                      name: grafana-data-volume
                  ports:
                    - containerPort: 3000
                      protocol: TCP
              volumes:
                - name: grafana-data-volume
                  emptyDir: {}
        
        EOF
        kubectl apply -f grafana.yml
.
        部署svc
        
        cat >grafana_svc.yml<<"EOF"
        kind: Service
        apiVersion: v1
        metadata:
          labels:
            app: grafana
          name: grafana-service
          namespace: prometheus-work
        spec:
          ports:
            - port: 3000
              targetPort: 3000
          selector:
            app: grafana
          type: NodePort
        
        EOF
        kubectl apply -f grafana_svc.yml
  
        查看服务
        
        [root@master1 ~]# kubectl get pod,svc -n prometheus-work |grep grafana
        pod/grafana-5d475d9d7-ctb2t      1/1     Running   0          5m18s
        service/grafana-service   NodePort   10.99.157.212   <none>        3000:31163/TCP   5m12s
        #查看grafana的pod在哪个节点
        [root@master1 1]# kubectl describe pod -n prometheus-work grafana-5d475d9d7-ctb2t | grep Node:
        Node:             node02/192.168.48.105
        [root@master1 1]#
        
        访问页面 http://XXX:31163

4.Kubernetes核心指标监控——Metrics Server
  1> 下载并部署Metrics Server
  wget https://github.com/kubernetes-sigs/metrics-server/releases/download/v0.6.2/components.yaml
  2> 验证Metrics Server组件部署成功
  [root@master1 metrics-server]# kubectl api-versions|grep metrics
    metrics.k8s.io/v1beta1

    [root@master1 ~]# kubectl get pods -n=kube-system |grep metrics
    metrics-server-855cc6b9d-g6xsf  1/1   Running  0     18h

    [root@master1 ~]# kubectl top nodes
    NAME      CPU(cores)   CPU%   MEMORY(bytes)   MEMORY%  
    master1   272m         3%     4272Mi          29%      
    node1     384m         5%     9265Mi          30%      
    node2     421m         5%     14476Mi         48%  
5. Configure Default CPU Requests and Limits for a Namespace
    Define a default CPU resource limits for a namespace, so that every new Pod in that namespace has a CPU resource limit configured.
    This page shows how to configure default CPU requests and limits for a namespace.
    
    A Kubernetes cluster can be divided into namespaces. If you create a Pod within a namespace that has a default CPU limit, and any container in that Pod does not specify its own CPU limit, then the control plane assigns the default CPU limit to that container.

    kubectl create namespace default-cpu-example
   apiVersion: v1
    kind: LimitRange
    metadata:
      name: cpu-limit-range
    spec:
      limits:
      - default:
          cpu: 1
        defaultRequest:
          cpu: 0.5
        type: Container

   kubectl apply -f https://k8s.io/examples/admin/resource/cpu-defaults.yaml --namespace=default-cpu-example


   apiVersion: v1
    kind: Pod
    metadata:
      name: default-cpu-demo
    spec:
      containers:
      - name: default-cpu-demo-ctr
        image: nginx
        
  kubectl apply -f https://k8s.io/examples/admin/resource/cpu-defaults-pod.yaml --namespace=default-cpu-example
  
  kubectl get pod default-cpu-demo --output=yaml --namespace=default-cpu-example

  6.Kubernetes 中部署 NFS Provisioner 为 NFS 提供动态分配卷
          # 清理rbac授权
        kubectl delete -f nfs-rbac.yaml -n kube-system
        
        # 编写yaml
        cat >nfs-rbac.yaml<<-EOF
        ---
        kind: ServiceAccount
        apiVersion: v1
        metadata:
          name: nfs-client-provisioner
        ---
        kind: ClusterRole
        apiVersion: rbac.authorization.k8s.io/v1
        metadata:
          name: nfs-client-provisioner-runner
        rules:
          - apiGroups: [""]
            resources: ["persistentvolumes"]
            verbs: ["get", "list", "watch", "create", "delete"]
          - apiGroups: [""]
            resources: ["persistentvolumeclaims"]
            verbs: ["get", "list", "watch", "update"]
          - apiGroups: ["storage.k8s.io"]
            resources: ["storageclasses"]
            verbs: ["get", "list", "watch"]
          - apiGroups: [""]
            resources: ["events"]
            verbs: ["create", "update", "patch"]
        ---
        kind: ClusterRoleBinding
        apiVersion: rbac.authorization.k8s.io/v1
        metadata:
          name: run-nfs-client-provisioner
        subjects:
          - kind: ServiceAccount
            name: nfs-client-provisioner
            namespace: kube-system
        roleRef:
          kind: ClusterRole
          name: nfs-client-provisioner-runner
          apiGroup: rbac.authorization.k8s.io
        ---
        kind: Role
        apiVersion: rbac.authorization.k8s.io/v1
        metadata:
          name: leader-locking-nfs-client-provisioner
        rules:
          - apiGroups: [""]
            resources: ["endpoints"]
            verbs: ["get", "list", "watch", "create", "update", "patch"]
        ---
        kind: RoleBinding
        apiVersion: rbac.authorization.k8s.io/v1
        metadata:
          name: leader-locking-nfs-client-provisioner
        subjects:
          - kind: ServiceAccount
            name: nfs-client-provisioner
            # replace with namespace where provisioner is deployed
            namespace: kube-system
        roleRef:
          kind: Role
          name: leader-locking-nfs-client-provisioner
          apiGroup: rbac.authorization.k8s.io
        EOF
        
        # 应用授权
        kubectl apply -f nfs-rbac.yaml -n kube-system


        git clone https://github.com/kubernetes-incubator/external-storage.git
        cp -R external-storage/nfs-client/deploy/ /root/
        cd deploy

        # 清理NFS Provisioner资源
        kubectl delete -f nfs-provisioner-deploy.yaml -n kube-system
        
        export NFS_ADDRESS='10.198.1.155'
        export NFS_DIR='/data/nfs'
        
        # 编写deployment.yaml
        cat >nfs-provisioner-deploy.yaml<<-EOF
        ---
        kind: Deployment
        apiVersion: apps/v1
        metadata:
          name: nfs-client-provisioner
        spec:
          replicas: 1
          selector:
            matchLabels:
              app: nfs-client-provisioner
          strategy:
            type: Recreate  #---设置升级策略为删除再创建(默认为滚动更新)
          template:
            metadata:
              labels:
                app: nfs-client-provisioner
            spec:
              serviceAccountName: nfs-client-provisioner
              containers:
                - name: nfs-client-provisioner
                  #---由于quay.io仓库国内被墙，所以替换成七牛云的仓库
                  #image: quay-mirror.qiniu.com/external_storage/nfs-client-provisioner:latest
                  image: registry.cn-hangzhou.aliyuncs.com/open-ali/nfs-client-provisioner:latest
                  volumeMounts:
                    - name: nfs-client-root
                      mountPath: /persistentvolumes
                  env:
                    - name: PROVISIONER_NAME
                      value: nfs-client  #---nfs-provisioner的名称，以后设置的storageclass要和这个保持一致
                    - name: NFS_SERVER
                      value: ${NFS_ADDRESS}  #---NFS服务器地址，和 valumes 保持一致
                    - name: NFS_PATH
                      value: ${NFS_DIR}  #---NFS服务器目录，和 valumes 保持一致
              volumes:
                - name: nfs-client-root
                  nfs:
                    server: ${NFS_ADDRESS}  #---NFS服务器地址
                    path: ${NFS_DIR} #---NFS服务器目录
        EOF
        
        # 部署deployment.yaml
        kubectl apply -f nfs-provisioner-deploy.yaml -n kube-system
        
        # 查看创建的pod
        kubectl get pod -o wide -n kube-system|grep nfs-client
        
        # 查看pod日志
        kubectl logs -f `kubectl get pod -o wide -n kube-system|grep nfs-client|awk '{print $1}'` -n kube-system
        # 清理storageclass资源
        kubectl delete -f nfs-storage.yaml
        
        # 编写yaml
        cat >nfs-storage.yaml<<-EOF
        apiVersion: storage.k8s.io/v1
        kind: StorageClass
        metadata:
          name: nfs-storage
          annotations:
            storageclass.kubernetes.io/is-default-class: "true"  #---设置为默认的storageclass
        provisioner: nfs-client  #---动态卷分配者名称，必须和上面创建的"PROVISIONER_NAME"变量中设置的Name一致
        parameters:
          archiveOnDelete: "true"  #---设置为"false"时删除PVC不会保留数据,"true"则保留数据
        mountOptions: 
          - hard        #指定为硬挂载方式
          - nfsvers=4   #指定NFS版本，这个需要根据 NFS Server 版本号设置
        EOF
        
        #部署class.yaml
        kubectl apply -f nfs-storage.yaml
        
        #查看创建的storageclass(这里可以看到nfs-storage已经变为默认的storageclass了)
        $ kubectl get sc
        NAME                    PROVISIONER      AGE
        nfs-storage (default)   nfs-client       3m38s
        
         创建 PVC
           # 删除命令空间
           kubectl delete ns kube-public
           
           # 创建命名空间
           kubectl create ns kube-public
           
           # 清理pvc
           kubectl delete -f test-claim.yaml -n kube-public
           
           # 编写yaml
           cat >test-claim.yaml<<\EOF
           kind: PersistentVolumeClaim
           apiVersion: v1
           metadata:
             name: test-claim
           spec:
             storageClassName: nfs-storage #---需要与上面创建的storageclass的名称一致
             accessModes:
               - ReadWriteMany
             resources:
               requests:
                 storage: 100Gi
           EOF
           
           #创建PVC
           kubectl apply -f test-claim.yaml -n kube-public
           
           #查看创建的PV和PVC
           $ kubectl get pvc -n kube-public
           NAME         STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   AGE
           test-claim   Bound    pvc-593f241f-a75f-459a-af18-a672e5090921   100Gi      RWX            nfs-storage    3s
           
           kubectl get pv
           
           #然后，我们进入到NFS的export目录，可以看到对应该volume name的目录已经创建出来了。其中volume的名字是namespace，PVC name以及uuid的组合：
           
           #注意，出现pvc在pending的原因可能为nfs-client-provisioner pod 出现了问题，删除重建的时候会出现镜像问题
         
         创建测试 Pod
           # 清理资源
           kubectl delete -f test-pod.yaml -n kube-public
           
           # 编写yaml
           cat > test-pod.yaml <<\EOF
           kind: Pod
           apiVersion: v1
           metadata:
             name: test-pod
           spec:
             containers:
             - name: test-pod
               image: busybox:latest
               command:
                 - "/bin/sh"
               args:
                 - "-c"
                 - "touch /mnt/SUCCESS && exit 0 || exit 1"
               volumeMounts:
                 - name: nfs-pvc
                   mountPath: "/mnt"
             restartPolicy: "Never"
             volumes:
               - name: nfs-pvc
                 persistentVolumeClaim:
                   claimName: test-claim
           EOF
           
           #创建pod
           kubectl apply -f test-pod.yaml -n kube-public
           
           #查看创建的pod
           kubectl get pod -o wide -n kube-public

7. 在 OpenWhisk 上部署 YOLO 以实现图片目标检测
   1> 定制带有 YOLO 的 OpenWhisk Python runtime 容器
   docker pull openwhisk/action-python-v3.11:latest
   FROM openwhisk/action-python-v3.11:latest
   # 安装 OpenCV 图形渲染所需的 OpenGL 库
   RUN apt update && apt install -y libgl1-mesa-glx
   # 此处安装 CPU 版的 PyTorch 为例
   RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
   # 安装 YOLO 库
   RUN pip install ultralytics
   # 创建模型文件夹
   RUN mkdir -p /models
   # 将模型文件复制到容器中
   COPY ./models/* /models/

   docker build -t openwhisk-yolov8n-runtime:1.0.0 .

   2> 测试定制 OpenWhisk Python runtime 容器
   docker run -d -p 127.0.0.1:80:8080/tcp --name=bloom_whisker --rm -it openwhisk-yolov8n-runtime:1.0.0

   {
    "value": {
        "name": "yoloTest",
        "main": "main",
        "binary": false,
           "code": "def main(args):\n\timport json\n\tfrom ultralytics import YOLO\n\tsource = args.get('url', None)\n\tmodel = YOLO('/models/yolov8n.pt')\n\tresults = model(source)\n\treturn {'result': str([json.loads(r.to_json()) for r in results])}"
       }
   }

      def main(args):
          import json
      
          from ultralytics import YOLO
      
          source = args.get("url", None)
          model = YOLO("/models/yolov8n.pt")
          results = model(source)
          return {"result": str([json.loads(r.to_json()) for r in results])}
      
      
          curl -d "@python-data-init-params.json" -H "Content-Type: application/json" http://localhost/init
      
         3> 将定制镜像推送到 Docker Hub
        docker tag openwhisk-yolov8n-runtime:1.0.0 <DockerHubUser>/openwhisk-yolov8n-runtime:1.0.0
      
      # Example
      docker tag openwhisk-yolov8n-runtime:1.0.0 liuzhaoze/openwhisk-yolov8n-runtime:1.0.0
      docker push <DockerHubUser>/openwhisk-yolov8n-runtime:1.0.0
      
      # Example
      docker push liuzhaoze/openwhisk-yolov8n-runtime:1.0.0
      
        4> 在 OpenWhisk 上配置定制 Python runtime 容器
        cp runtimes.json runtimes.json.bak
        cp runtimes-minimal-travis.json runtimes-minimal-travis.json.bak
      
      测试
      def main(args):
          import json
      
          from ultralytics import YOLO
      
          source = args.get("url", None)
          model = YOLO("/models/yolov8n.pt")
          results = model(source)
          return {"result": str([json.loads(r.to_json()) for r in results])}
        
        zip -j -r yoloTest.zip yoloTest/
      
        sudo wsk -i action create yoloTest yoloTest.zip --kind python:3
        sudo wsk -i action invoke --result yoloTest --param url "https://ultralytics.com/images/bus.jpg"
      
         
      
         
