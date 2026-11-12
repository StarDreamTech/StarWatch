import { createRouter, createWebHistory } from 'vue-router'
import type { ModuleId } from '@/lib/navigation'
import type { TaskType } from '@/types/api'

declare module 'vue-router' {
  interface RouteMeta {
    title: string
    description: string
    module: ModuleId
    crumbs: string[]
    taskType?: TaskType
  }
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'overview',
      component: () => import('@/views/OverviewView.vue'),
      meta: {
        title: '总览',
        description: '今天的任务、运行和需要处理的异常。',
        module: 'overview',
        crumbs: ['总览'],
      },
    },
    {
      path: '/pages',
      name: 'pages',
      component: () => import('@/views/TaskListView.vue'),
      meta: {
        title: '网页监控',
        description: '比较你指定的字段，而不是整页哈希。',
        module: 'pages',
        crumbs: ['网页监控'],
        taskType: 'page_change',
      },
    },
    {
      path: '/pages/new',
      name: 'pages-new',
      component: () => import('@/views/TaskFormView.vue'),
      meta: {
        title: '新建网页监控',
        description: '用 CSS、XPath、JSONPath 或正则取出要盯住的字段。',
        module: 'pages',
        crumbs: ['网页监控', '新建'],
        taskType: 'page_change',
      },
    },
    {
      path: '/pages/:id',
      name: 'pages-edit',
      component: () => import('@/views/TaskFormView.vue'),
      meta: {
        title: '编辑网页监控',
        description: '修改调度、请求和提取规则。',
        module: 'pages',
        crumbs: ['网页监控', '编辑'],
        taskType: 'page_change',
      },
    },
    {
      path: '/checks',
      name: 'checks',
      component: () => import('@/views/TaskListView.vue'),
      meta: {
        title: '接口探活',
        description: '检查状态码、耗时、正文和响应头。',
        module: 'checks',
        crumbs: ['接口探活'],
        taskType: 'api_check',
      },
    },
    {
      path: '/checks/new',
      name: 'checks-new',
      component: () => import('@/views/TaskFormView.vue'),
      meta: {
        title: '新建接口探活',
        description: '为接口写下期望的状态、耗时或正文。',
        module: 'checks',
        crumbs: ['接口探活', '新建'],
        taskType: 'api_check',
      },
    },
    {
      path: '/checks/:id',
      name: 'checks-edit',
      component: () => import('@/views/TaskFormView.vue'),
      meta: {
        title: '编辑接口探活',
        description: '修改探活请求和断言。',
        module: 'checks',
        crumbs: ['接口探活', '编辑'],
        taskType: 'api_check',
      },
    },
    {
      path: '/load',
      name: 'load',
      component: () => import('@/views/TaskListView.vue'),
      meta: {
        title: '压力测试',
        description: '按并发和速率发送一批请求，并保留延迟汇总。',
        module: 'load',
        crumbs: ['压力测试'],
        taskType: 'load_test',
      },
    },
    {
      path: '/load/new',
      name: 'load-new',
      component: () => import('@/views/TaskFormView.vue'),
      meta: {
        title: '新建压力测试',
        description: '保存启用中的压测前会再次确认。',
        module: 'load',
        crumbs: ['压力测试', '新建'],
        taskType: 'load_test',
      },
    },
    {
      path: '/load/:id',
      name: 'load-edit',
      component: () => import('@/views/TaskFormView.vue'),
      meta: {
        title: '编辑压力测试',
        description: '调整并发、QPS 和停止条件。',
        module: 'load',
        crumbs: ['压力测试', '编辑'],
        taskType: 'load_test',
      },
    },
    {
      path: '/alerts',
      name: 'alerts',
      component: () => import('@/views/AlertsView.vue'),
      meta: {
        title: '告警通知',
        description: '变化、失败和拦截都会留在这里，外部通道另记投递结果。',
        module: 'alerts',
        crumbs: ['告警通知'],
      },
    },
    {
      path: '/plugins',
      name: 'plugins',
      component: () => import('@/views/PluginsView.vue'),
      meta: {
        title: '插件与代理',
        description: '请求器、代理、提取器和通知都从注册表读取。',
        module: 'plugins',
        crumbs: ['插件与代理'],
      },
    },
    {
      path: '/runs',
      name: 'runs',
      component: () => import('@/views/RunListView.vue'),
      meta: {
        title: '运行记录',
        description: '每次执行都保留结果。拦截、空页面和超时不会被写成无变化。',
        module: 'runs',
        crumbs: ['运行记录'],
      },
    },
    {
      path: '/runs/:id',
      name: 'run-detail',
      component: () => import('@/views/RunDetailView.vue'),
      meta: {
        title: '运行详情',
        description: '查看差异、响应和压测汇总。',
        module: 'runs',
        crumbs: ['运行记录', '详情'],
      },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
      meta: {
        title: '设置',
        description: '外观保存在这台浏览器里，服务配置来自环境变量。',
        module: 'settings',
        crumbs: ['设置'],
      },
    },
  ],
})

router.afterEach((to) => {
  document.title = `${to.meta.title} · 星哨`
})

export default router
