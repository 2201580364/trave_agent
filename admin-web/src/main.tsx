import React from 'react'
import ReactDOM from 'react-dom/client'
import { App as AntApp, ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import 'antd/dist/reset.css'

import { App } from './app/App'
import './app/styles.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#0f766e',
          colorInfo: '#0f766e',
          colorSuccess: '#15803d',
          colorWarning: '#d97706',
          colorError: '#dc2626',
          colorText: '#17312d',
          colorTextSecondary: '#657b76',
          colorBgLayout: '#f3f7f6',
          colorBgContainer: '#ffffff',
          colorBorderSecondary: '#e4ece9',
          borderRadius: 12,
          borderRadiusLG: 18,
          controlHeight: 40,
          boxShadowSecondary: '0 16px 40px rgba(22, 71, 62, 0.08)',
          fontFamily:
            "Inter, 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif",
        },
        components: {
          Button: {
            borderRadius: 10,
            primaryShadow: '0 8px 20px rgba(15, 118, 110, 0.18)',
          },
          Card: {
            headerBg: 'transparent',
          },
          Menu: {
            darkItemBg: 'transparent',
            darkSubMenuItemBg: 'transparent',
            darkItemSelectedBg: 'rgba(255, 255, 255, 0.14)',
            itemBorderRadius: 12,
          },
          Table: {
            headerBg: '#f6faf8',
            headerColor: '#34544e',
            rowHoverBg: '#f4fbf8',
          },
          Tabs: {
            itemSelectedColor: '#0f766e',
            inkBarColor: '#0f766e',
          },
        },
      }}
    >
      <AntApp>
        <App />
      </AntApp>
    </ConfigProvider>
  </React.StrictMode>,
)
