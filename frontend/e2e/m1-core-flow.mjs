/** H3 / S8-4: run against an existing in-app browser tab, never launch a browser.
 * The adapter uses the shared Playwright locator API: { page, reload }.
 * Requires a logged-in guest on trip-time with three valid configured dates.
 * Writes a test draft, intent, trip and read-only share to the configured DB.
 * Does not fabricate feedback or alter the published catalog.
 */
export const tenPlaces = [
  '灵隐寺', '飞来峰景区', '西溪国家湿地公园', '断桥残雪',
  '浙江省博物馆孤山馆区', '平湖秋月', '清河坊历史文化特色街区',
  '钱江新城灯光秀', '武林夜市', '杭州运河游船',
]

const timeoutMs = 30_000
async function visible(locator) {
  await locator.waitFor({ state: 'visible', timeoutMs })
}
function check(condition, message) {
  if (!condition) throw new Error(`M1 E2E: ${message}`)
}

export async function submitTenPlaceTrip({ page, reload }, { refreshWhilePending = false } = {}) {
  await visible(page.getByText('先确定旅行边界', { exact: true }))
  await page.getByText('选择想去的景点', { exact: true }).click()
  await visible(page.getByText(tenPlaces[0], { exact: true }))
  check(await page.locator('.attraction-card--selected').count() === 0, 'start with an empty new draft')
  for (const name of tenPlaces) await page.getByText(name, { exact: true }).click()
  check(await page.locator('.attraction-card--selected').count() === 10, 'ten distinct places selected')
  await page.getByText('确认选择', { exact: true }).click()
  await visible(page.getByText('确认后开始安排', { exact: true }))
  await page.getByText('生成我的行程', { exact: true }).click()
  if (refreshWhilePending) {
    await visible(page.getByText('正在获取交通并规划行程，刷新后会继续恢复同一任务。', { exact: true }))
    await reload()
  }
  return { selected: tenPlaces.length, submitted: true }
}

export async function submitReplacement({ page, reload }, replacementName) {
  await page.getByText('替换景点', { exact: true }).filter({ visible: true }).first().click()
  await visible(page.getByText(replacementName, { exact: true }))
  await page.getByText(replacementName, { exact: true }).click()
  await page.getByText('替换并重新规划', { exact: true }).click()
  await visible(page.getByText('正在重新规划，刷新后会继续恢复同一任务。', { exact: true }))
  await reload()
  return { replacementSubmitted: true, refreshedWhilePending: true }
}

/** Call again after pending generation completes; a timeout is not a pass. */
export async function verifyThreeDayTrip({ page, reload }) {
  await visible(page.locator('.timeline-item').first())
  check(await page.locator('.day-tab').count() === 3, 'three days must be visible')
  const readDays = async () => {
    const days = []
    for (let day = 0; day < 3; day += 1) {
      await page.locator('.day-tab').nth(day).click()
      await visible(page.locator('.timeline-item').first())
      days.push(await page.locator('.timeline-item').allTextContents({ timeoutMs }))
    }
    return days
  }
  const before = await readDays()
  const flat = before.flat().join('\n')
  check(before.flat().length === 10, 'ten visits across three days')
  for (const name of tenPlaces) check(flat.includes(name), `missing ${name}`)
  check(flat.includes('70 分钟') && flat.includes('150 分钟'), 'corrected published durations')
  check(!await page.getByText('本日暂无景点安排，可调整日期或景点后重新生成。', { exact: true }).isVisible(), 'no empty final day')
  await reload()
  await visible(page.locator('.timeline-item').first())
  const after = await readDays()
  check(JSON.stringify(before) === JSON.stringify(after), 'refresh must restore the same visits and times')
  return { days: before, refreshStable: true }
}

export async function verifyHistoryAndShare({ page }) {
  await page.getByText('历史版本', { exact: true }).click()
  await visible(page.getByText('查看当前版本', { exact: true }))
  await page.getByText('查看当前版本', { exact: true }).click()
  await visible(page.locator('.timeline-item').first())
  await page.getByText('分享计划', { exact: true }).click()
  await visible(page.getByText('生成安全分享预览', { exact: true }))
  await page.getByText('生成安全分享预览', { exact: true }).click()
  await visible(page.getByText('查看访客页面', { exact: true }))
  await page.getByText('查看访客页面', { exact: true }).click()
  await visible(page.getByText('以此为参考新建行程', { exact: true }))
  check(await page.getByText('替换景点', { exact: true }).filter({ visible: true }).count() === 0, 'public share cannot edit original visits')
  return { history: true, sharePreview: true, publicReadOnly: true }
}
