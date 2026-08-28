import { Button, Textarea, View } from '@tarojs/components'
import { useState } from 'react'

import './feedback.css'

import type { FeedbackResponse } from '@/entities/planning/types'
import { apiRequest } from '@/shared/api/client'

type TripRating = 'reasonable' | 'neutral' | 'unreasonable'

interface TripFeedbackPanelProps {
  token: string
  tripId: string
  revisionId: string
  revisionNumber: number
}

const ratingOptions: Array<[TripRating, string]> = [
  ['reasonable', '合理'],
  ['neutral', '一般'],
  ['unreasonable', '不合理']
]

const problemOptions = [
  ['route_too_long', '路线太绕'],
  ['time_unreasonable', '时间安排不合理'],
  ['pace_mismatch', '节奏太紧或太松'],
  ['missing_attraction', '漏掉想去的景点'],
  ['attraction_data_error', '景点数据有误'],
  ['explanation_unclear', '原因解释不清']
] as const

function newIntentId(prefix: string) {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`
}

export function TripFeedbackPanel({ token, tripId, revisionId, revisionNumber }: TripFeedbackPanelProps) {
  const [rating, setRating] = useState<TripRating | ''>('')
  const [problemTypes, setProblemTypes] = useState<string[]>([])
  const [comment, setComment] = useState('')
  const [pendingIntent, setPendingIntent] = useState<{ id: string; fingerprint: string } | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [deduplicated, setDeduplicated] = useState(false)
  const [error, setError] = useState('')

  const chooseRating = (value: TripRating) => {
    setRating(value)
    if (value === 'reasonable') setProblemTypes([])
  }

  const toggleProblem = (value: string) => {
    setProblemTypes((current) => current.includes(value)
      ? current.filter((item) => item !== value)
      : [...current, value])
  }

  const submit = async () => {
    if (!rating || submitting) return
    const normalizedProblems = [...problemTypes].sort()
    const normalizedComment = comment.trim()
    const fingerprint = JSON.stringify([rating, normalizedProblems, normalizedComment])
    const intent = pendingIntent?.fingerprint === fingerprint
      ? pendingIntent
      : { id: newIntentId('feedback_trip'), fingerprint }
    if (intent !== pendingIntent) setPendingIntent(intent)
    setSubmitting(true)
    setError('')
    try {
      const response = await apiRequest<FeedbackResponse>(
        `/api/v1/trips/${tripId}/feedback`,
        {
          method: 'POST',
          token,
          data: {
            feedback_intent_id: intent.id,
            revision_id: revisionId,
            rating,
            problem_types: normalizedProblems,
            comment: normalizedComment || null
          }
        }
      )
      setDeduplicated(response.deduplicated)
      setSubmitted(true)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '反馈提交失败，请稍后重试。')
    } finally {
      setSubmitting(false)
    }
  }

  if (submitted) {
    return (
      <View className='card feedback-panel'>
        <View className='section-title'>这份安排对你来说合理吗？</View>
        <View className='feedback-success'>✓ {deduplicated ? '此版本的反馈已经记录，未重复提交。' : `已记录你对第 ${revisionNumber} 版行程的反馈。`}</View>
        <View className='field-help'>反馈只用于改进行程安排，不会变成公开景点评分或评论。</View>
      </View>
    )
  }

  return (
    <View className='card feedback-panel'>
      <View>
        <View className='section-title'>这份安排对你来说合理吗？</View>
        <View className='field-help'>评价的是当前第 {revisionNumber} 版行程，不是景点本身。</View>
      </View>
      <View className='feedback-choice-row'>
        {ratingOptions.map(([value, label]) => (
          <Button
            key={value}
            className={`feedback-choice ${rating === value ? 'feedback-choice--active' : ''}`}
            onClick={() => chooseRating(value)}
          >
            {label}
          </Button>
        ))}
      </View>
      {rating && rating !== 'reasonable' && (
        <View>
          <View className='field-label'>哪里需要改进？（可多选）</View>
          <View className='feedback-reason-grid'>
            {problemOptions.map(([value, label]) => (
              <Button
                key={value}
                className={`feedback-reason ${problemTypes.includes(value) ? 'feedback-reason--active' : ''}`}
                onClick={() => toggleProblem(value)}
              >
                {label}
              </Button>
            ))}
          </View>
        </View>
      )}
      {rating && (
        <Textarea
          className='feedback-comment'
          maxlength={500}
          value={comment}
          placeholder='补充说明（可选，请勿填写手机号、票号等敏感信息）'
          onInput={(event) => setComment(event.detail.value)}
        />
      )}
      {error && <View className='error'>{error}</View>}
      <Button
        className='primary feedback-submit'
        loading={submitting}
        disabled={!rating || submitting}
        onClick={submit}
      >
        提交整体反馈
      </Button>
    </View>
  )
}
