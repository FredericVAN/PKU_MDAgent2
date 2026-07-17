# lammps-frontend

This template should help get you started developing with Vue 3 in Vite.

## Recommended IDE Setup

[VSCode](https://code.visualstudio.com/) + [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar) (and disable Vetur).

## Customize configuration

See [Vite Configuration Reference](https://vite.dev/config/).

## Project Setup

```sh
npm install
```

### Compile and Hot-Reload for Development

```sh
npm run dev
```

### 启动开发服务器并允许外部访问

本项目已配置端口为20198，并允许外部设备访问。

```sh
npm run dev
```

- 本机访问地址: http://localhost:20198
- 局域网/外部访问: http://<你的IP>:20198

> 如需外部访问，请确保服务器20198端口已放行（如关闭防火墙或添加入站规则）。

#### 配置后端地址

前端通过环境变量 `VITE_API_BASE` 决定请求哪个后端，默认值在 `.env` 中为 `http://localhost:8000`。

局域网/生产部署时，请勿直接修改 `.env`，而是新建 `.env.local`（已被 git 忽略）覆盖，例如：

```
VITE_API_BASE=http://<服务器局域网IP>:8000
```

否则局域网内其他设备访问前端时，浏览器会向"自己"的 8000 端口发请求而不是服务器，导致连接失败。

### Compile and Minify for Production

```sh
npm run build
```
