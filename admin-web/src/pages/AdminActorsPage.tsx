import { PlusOutlined, ReloadOutlined, SafetyCertificateOutlined } from '@ant-design/icons'
import {
  App,
  Button,
  Card,
  Checkbox,
  Descriptions,
  Form,
  Input,
  Modal,
  Space,
  Table,
  Tag,
  Typography,
  type TableColumnsType,
} from 'antd'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { AdminApiError, createOperationIntent } from '../api/adminApi'
import { adminErrorMessage } from '../api/errorMessages'
import type { AdminActor, CreateAdminActorInput, ReplaceAdminRolesInput } from '../api/types'
import { useAdminSession } from '../auth/AdminSessionProvider'
import { ErrorNotice } from '../components/ErrorNotice'
import { HighRiskConfirm } from '../components/HighRiskConfirm'

const ROLE_CATALOG = [
  { key: 'data_editor', label: '数据编辑', description: '候选地点与修订版本编辑、送审' },
  { key: 'data_reviewer', label: '数据审核', description: '修订版本审核决定' },
  { key: 'data_publisher', label: '数据发布', description: '发布门与研究快照' },
  { key: 'research_viewer', label: '研究只读', description: '研究快照只读访问' },
  { key: 'admin_security', label: '安全管理', description: '管理员、角色与审计' },
  {
    key: 'content_moderator',
    label: '内容治理',
    description: 'OM3 才启用',
    disabled: true,
  },
] as const

const ROLE_LABELS = Object.fromEntries(ROLE_CATALOG.map((role) => [role.key, role.label]))

type ActorFormFields = {
  login_name: string
  initial_password: string
  role_keys: string[]
  reason_code: string
  reason_text?: string
}

type RoleFormFields = {
  role_keys: string[]
  reason_code: string
  reason_text?: string
}

type PendingRoleChange = {
  actor: AdminActor
  values: RoleFormFields
  operationIntentId: string
}

export function AdminActorsPage() {
  const { api, hasPermission, principal } = useAdminSession()
  const { message } = App.useApp()
  const [actors, setActors] = useState<AdminActor[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [createLoading, setCreateLoading] = useState(false)
  const [createIntent, setCreateIntent] = useState('')
  const [roleActor, setRoleActor] = useState<AdminActor | null>(null)
  const [roleIntent, setRoleIntent] = useState('')
  const [pendingRoleChange, setPendingRoleChange] = useState<PendingRoleChange | null>(null)
  const [roleLoading, setRoleLoading] = useState(false)
  const [createForm] = Form.useForm<ActorFormFields>()
  const [roleForm] = Form.useForm<RoleFormFields>()
  const canWrite = hasPermission('admin:actor:roles:write')

  const loadActors = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await api.listAdminActors()
      setActors(response.items)
    } catch (reason) {
      setError(adminErrorMessage(reason))
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => {
    void loadActors()
  }, [loadActors])

  const openCreate = () => {
    setCreateIntent(createOperationIntent('admin-create'))
    createForm.resetFields()
    createForm.setFieldsValue({ role_keys: ['data_editor'] })
    setCreateOpen(true)
  }

  const submitCreate = async (values: ActorFormFields) => {
    setCreateLoading(true)
    setError(null)
    const payload: CreateAdminActorInput = {
      operation_intent_id: createIntent,
      login_name: values.login_name,
      initial_password: values.initial_password,
      role_keys: values.role_keys,
      reason_code: values.reason_code,
      reason_text: values.reason_text?.trim() || null,
    }
    try {
      const created = await api.createAdminActor(payload)
      message.success(created.reused ? '已识别为同一操作，未重复创建。' : '管理员已创建。')
      setCreateOpen(false)
      createForm.resetFields()
      await loadActors()
    } catch (reason) {
      setError(adminErrorMessage(reason))
    } finally {
      setCreateLoading(false)
    }
  }

  const openRoleEditor = (actor: AdminActor) => {
    setRoleActor(actor)
    setRoleIntent(createOperationIntent('admin-roles'))
    roleForm.setFieldsValue({
      role_keys: actor.role_keys,
      reason_code: '',
      reason_text: '',
    })
  }

  const stageRoleChange = (values: RoleFormFields) => {
    if (roleActor === null) return
    setPendingRoleChange({ actor: roleActor, values, operationIntentId: roleIntent })
    setRoleActor(null)
  }

  const confirmRoleChange = async () => {
    if (pendingRoleChange === null) return
    setRoleLoading(true)
    setError(null)
    const { actor, values, operationIntentId } = pendingRoleChange
    const payload: ReplaceAdminRolesInput = {
      operation_intent_id: operationIntentId,
      expected_version: actor.version,
      role_keys: values.role_keys,
      reason_code: values.reason_code,
      reason_text: values.reason_text?.trim() || null,
    }
    try {
      const changed = await api.replaceAdminRoles(actor.admin_actor_id, payload)
      message.success(
        changed.reused ? '已识别为同一操作，未重复变更。' : '角色已更新，目标管理员旧会话已失效。',
      )
      setPendingRoleChange(null)
      roleForm.resetFields()
      await loadActors()
    } catch (reason) {
      setError(adminErrorMessage(reason))
      setPendingRoleChange(null)
      if (reason instanceof AdminApiError && reason.code === 'admin_actor_version_conflict') {
        await loadActors()
      }
    } finally {
      setRoleLoading(false)
    }
  }

  const columns = useMemo<TableColumnsType<AdminActor>>(
    () => [
      {
        title: '管理员',
        dataIndex: 'login_name',
        fixed: 'left',
        width: 190,
        render: (value: string, actor) => (
          <Space orientation="vertical" size={0}>
            <Typography.Text strong>{value}</Typography.Text>
            {actor.admin_actor_id === principal?.admin_actor_id && <Tag color="blue">当前账号</Tag>}
          </Space>
        ),
      },
      {
        title: '状态',
        dataIndex: 'status',
        width: 100,
        render: (status: AdminActor['status']) => (
          <Tag color={status === 'active' ? 'success' : status === 'locked' ? 'error' : 'default'}>
            {status === 'active' ? '有效' : status === 'locked' ? '已锁定' : '已停用'}
          </Tag>
        ),
      },
      {
        title: '角色',
        dataIndex: 'role_keys',
        width: 360,
        render: (roles: string[]) => (
          <Space size={[4, 4]} wrap>
            {roles.map((role) => (
              <Tag key={role} color={role === 'admin_security' ? 'gold' : 'default'}>
                {ROLE_LABELS[role] ?? '未识别角色'}
              </Tag>
            ))}
          </Space>
        ),
      },
      { title: '资料版本', dataIndex: 'version', width: 100 },
      { title: '会话版本', dataIndex: 'session_version', width: 100 },
      {
        title: '更新时间',
        dataIndex: 'updated_at',
        width: 190,
        render: formatDateTime,
      },
      ...(canWrite
        ? [
            {
              title: '操作',
              key: 'actions',
              fixed: 'right' as const,
              width: 120,
              render: (_: unknown, actor: AdminActor) => (
                <Button onClick={() => openRoleEditor(actor)}>调整角色</Button>
              ),
            },
          ]
        : []),
    ],
    [canWrite, principal?.admin_actor_id],
  )

  return (
        <Space orientation="vertical" size="large" style={{ width: '100%' }}>
      <div className="page-heading-row">
        <div>
          <Typography.Title level={2}>管理员与角色</Typography.Title>
          <Typography.Paragraph type="secondary">
            O16 · 管理员身份独立于普通用户。角色变更采用乐观锁、二次确认和追加式审计。
          </Typography.Paragraph>
        </div>
        <Space wrap>
          <Button icon={<ReloadOutlined />} onClick={() => void loadActors()} loading={loading}>
            刷新
          </Button>
          {canWrite && (
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
              创建管理员
            </Button>
          )}
        </Space>
      </div>
      {error !== null && <ErrorNotice message={error} onClose={() => setError(null)} />}
      <Card>
        <Table<AdminActor>
          rowKey="admin_actor_id"
          loading={loading}
          columns={columns}
          dataSource={actors}
          pagination={false}
          scroll={{ x: 1100 }}
          locale={{ emptyText: '暂无可见管理员' }}
          expandable={{
            expandedRowRender: (actor) => (
              <Descriptions size="small" column={{ xs: 1, sm: 2 }}>
                <Descriptions.Item label="管理员 ID">{actor.admin_actor_id}</Descriptions.Item>
                <Descriptions.Item label="创建时间">{formatDateTime(actor.created_at)}</Descriptions.Item>
              </Descriptions>
            ),
          }}
        />
      </Card>

      <Modal
        open={createOpen}
        title="创建管理员"
        okText="创建"
        confirmLoading={createLoading}
        onOk={() => createForm.submit()}
        onCancel={() => !createLoading && setCreateOpen(false)}
        destroyOnHidden
      >
        <Typography.Paragraph type="secondary">
          初始密码只在本次表单中使用，提交后不会回显。请通过受控渠道交付，不要写入操作理由。
        </Typography.Paragraph>
        <Form<ActorFormFields>
          form={createForm}
          layout="vertical"
          requiredMark="optional"
          onFinish={(values) => void submitCreate(values)}
        >
          <Form.Item
            name="login_name"
            label="登录名"
            rules={[
              { required: true, min: 3, max: 64 },
              { pattern: /^[a-z0-9][a-z0-9._-]+$/, message: '仅使用小写字母、数字、点、下划线或短横线' },
            ]}
          >
            <Input autoComplete="off" />
          </Form.Item>
          <Form.Item
            name="initial_password"
            label="初始密码"
            rules={[{ required: true, min: 14, max: 256, message: '初始密码至少 14 位' }]}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
          <RoleCheckboxes />
          <ReasonFields />
        </Form>
      </Modal>

      <Modal
        open={roleActor !== null}
        title={`调整角色：${roleActor?.login_name ?? ''}`}
        okText="进入安全确认"
        onOk={() => roleForm.submit()}
        onCancel={() => setRoleActor(null)}
        destroyOnHidden
      >
        <Typography.Paragraph type="warning">
          角色保存后，该管理员所有旧会话立即失效。最后一个有效安全管理员受服务端保护。
        </Typography.Paragraph>
        <Form<RoleFormFields>
          form={roleForm}
          layout="vertical"
          requiredMark="optional"
          onFinish={stageRoleChange}
        >
          <RoleCheckboxes />
          <ReasonFields />
        </Form>
      </Modal>

      <HighRiskConfirm
        open={pendingRoleChange !== null}
        title="确认高风险角色变更"
        description={`此操作会替换 ${pendingRoleChange?.actor.login_name ?? ''} 的全部角色，并立即使其旧会话失效。`}
        confirmationText={pendingRoleChange?.actor.login_name ?? ''}
        loading={roleLoading}
        onConfirm={() => void confirmRoleChange()}
        onCancel={() => !roleLoading && setPendingRoleChange(null)}
      />
    </Space>
  )
}

function RoleCheckboxes() {
  return (
    <Form.Item
      name="role_keys"
      label="角色"
      rules={[{ required: true, type: 'array', min: 1, message: '至少选择一个角色' }]}
    >
      <Checkbox.Group style={{ width: '100%' }}>
        <Space orientation="vertical" style={{ width: '100%' }}>
          {ROLE_CATALOG.map((role) => (
            <Checkbox key={role.key} value={role.key} disabled={'disabled' in role && role.disabled}>
              <Space>
                <span>{role.label}</span>
                <Typography.Text type="secondary">{role.description}</Typography.Text>
              </Space>
            </Checkbox>
          ))}
        </Space>
      </Checkbox.Group>
    </Form.Item>
  )
}

function ReasonFields() {
  return (
    <>
      <Form.Item
        name="reason_code"
        label="理由代码"
        rules={[
          { required: true, message: '请输入稳定理由代码' },
          { pattern: /^[A-Z][A-Z0-9_]{2,63}$/, message: '使用 3–64 位大写字母、数字和下划线' },
        ]}
      >
        <Input placeholder="例如 OM1_TEAM_PROVISIONING" autoComplete="off" />
      </Form.Item>
      <Form.Item
        name="reason_text"
        label="补充说明（非敏感，可选）"
        rules={[{ max: 500, message: '最多 500 字' }]}
      >
        <Input.TextArea
          rows={3}
          placeholder="不得填写密码、Token、API Key、Cookie、私钥或第三方页面全文"
          autoComplete="off"
        />
      </Form.Item>
    </>
  )
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'medium',
    hour12: false,
  }).format(new Date(value))
}
