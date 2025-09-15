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
