import { Button, Textarea, View } from '@tarojs/components'
import { useState } from 'react'

import './feedback.css'

import type { FeedbackResponse } from '@/entities/planning/types'
import { apiRequest } from '@/shared/api/client'

type NodeRating = 'like' | 'dislike'

interface NodeFeedbackControlProps {
  token: string
  tripId: string
  revisionId: string
  nodeId: string
  nodeName: string
}

const negativeReasons = [
  ['time_too_tight', '时间太赶'],
  ['travel_too_far', '路程太远'],
  ['time_period_wrong', '时段不合适'],
  ['duration_wrong', '停留时长不合适'],
  ['attraction_data_error', '景点数据有误']
] as const

function newNodeIntentId() {
  return `feedback_node_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
}

export function NodeFeedbackControl({ token, tripId, revisionId, nodeId, nodeName }: NodeFeedbackControlProps) {
  const [rating, setRating] = useState<NodeRating | ''>('')
  const [reasonCode, setReasonCode] = useState('')
  const [comment, setComment] = useState('')
  const [pendingIntent, setPendingIntent] = useState<{ id: string; fingerprint: string } | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [deduplicated, setDeduplicated] = useState(false)
  const [error, setError] = useState('')

  const chooseRating = (value: NodeRating) => {
    setRating(value)
    setReasonCode(value === 'like' ? 'arrangement_good' : '')
  }

  const submit = async () => {
    if (!rating || submitting) return
    const normalizedComment = comment.trim()
    const fingerprint = JSON.stringify([rating, reasonCode, normalizedComment])
    const intent = pendingIntent?.fingerprint === fingerprint
      ? pendingIntent
      : { id: newNodeIntentId(), fingerprint }
    if (intent !== pendingIntent) setPendingIntent(intent)
    setSubmitting(true)
    setError('')
    try {
      const response = await apiRequest<FeedbackResponse>(
        `/api/v1/trips/${tripId}/revisions/${revisionId}/nodes/${nodeId}/feedback`,
        {
          method: 'POST',
          token,
          data: {
            feedback_intent_id: intent.id,
            rating,
            reason_code: reasonCode || null,
            comment: normalizedComment || null
          }
        }
      )
      setDeduplicated(response.deduplicated)
      setSubmitted(true)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '节点反馈提交失败。')
    } finally {
      setSubmitting(false)
    }
  }

  if (submitted) {
    return (
      <View className='node-feedback'>
        <View className='feedback-success'>✓ {deduplicated ? '这处安排已经反馈过。' : '已记录这处安排的反馈。'}</View>
      </View>
    )
  }

  return (
    <View className='node-feedback'>
      <View className='node-feedback-title'>这处安排怎么样？</View>
      <View className='node-feedback-actions'>
        <Button
          className={`node-feedback-choice ${rating === 'like' ? 'node-feedback-choice--active' : ''}`}
          onClick={() => chooseRating('like')}
        >
          👍 安排得好
        </Button>
        <Button
          className={`node-feedback-choice ${rating === 'dislike' ? 'node-feedback-choice--active' : ''}`}
          onClick={() => chooseRating('dislike')}
        >
          👎 需要改进
        </Button>
      </View>
      {rating && (
        <View className='node-feedback-details'>
          {rating === 'dislike' && (
            <View className='feedback-reason-grid'>
              {negativeReasons.map(([value, label]) => (
                <Button
                  key={value}
                  className={`feedback-reason ${reasonCode === value ? 'feedback-reason--active' : ''}`}
                  onClick={() => setReasonCode(reasonCode === value ? '' : value)}
                >
                  {label}
                </Button>
              ))}
            </View>
          )}
          <Textarea
            className='feedback-comment'
            maxlength={500}
            value={comment}
            placeholder={`补充对“${nodeName}”安排的说明（可选）`}
            onInput={(event) => setComment(event.detail.value)}
          />
          {error && <View className='error'>{error}</View>}
          <Button
            className='secondary feedback-submit'
            loading={submitting}
            disabled={submitting}
            onClick={submit}
          >
            提交这处反馈
          </Button>
        </View>
      )}
    </View>
  )
}
