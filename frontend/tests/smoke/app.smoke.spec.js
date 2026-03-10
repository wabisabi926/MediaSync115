import { expect, test } from '@playwright/test'

async function waitForPageReady(page) {
  await page.waitForLoadState('domcontentloaded')
  await page.waitForLoadState('networkidle', { timeout: 20_000 }).catch(() => {})
}

test.describe('前端烟雾测试', () => {
  test('豆瓣探索首页可以渲染首屏榜单', async ({ page }) => {
    await page.goto('/explore/douban')
    await waitForPageReady(page)

    await expect(page.getByRole('heading', { name: '豆瓣榜单探索' })).toBeVisible()
    await expect(page.locator('.recommend-group').first()).toBeVisible()
    await expect(page.locator('.recommend-card').first()).toBeVisible()
  })

  test('更多榜单页面可以渲染卡片列表', async ({ page }) => {
    await page.goto('/explore/douban/section/movie_hot')
    await waitForPageReady(page)

    await expect(page.getByRole('button', { name: '返回探索' })).toBeVisible()
    await expect(page.locator('.movie-card').first()).toBeVisible()
    await expect(page.locator('.load-anchor')).toBeVisible()
  })

  test('电影详情页可以打开并展示资源页签', async ({ page }) => {
    await page.goto('/movie/272')
    await waitForPageReady(page)

    await expect(page.locator('.movie-detail-page h1.title')).toBeVisible()
    await expect(page.getByRole('tab', { name: '115网盘' })).toBeVisible()
    await expect(page.getByRole('tab', { name: '磁力链接' })).toBeVisible()
    await expect(page.getByRole('tab', { name: 'ED2K' })).toBeVisible()
    await expect(page.getByRole('button', { name: /用 Nullbr 获取资源|刷新 Nullbr/ })).toBeVisible()

    await page.getByRole('tab', { name: 'HDHive' }).click()
    await expect(page.getByRole('button', { name: /用 HDHive 获取资源|刷新 HDHive/ })).toBeVisible()
  })

  test('剧集详情页可以打开并展示选集相关操作', async ({ page }) => {
    await page.goto('/tv/1399')
    await waitForPageReady(page)

    await expect(page.locator('.tv-detail-page h1.title')).toBeVisible()
    await expect(page.getByRole('tab', { name: '115网盘' })).toBeVisible()
    await expect(page.getByRole('button', { name: /用 Nullbr 获取资源|刷新 Nullbr/ })).toBeVisible()

    await page.getByRole('tab', { name: 'HDHive' }).click()
    await expect(page.getByRole('button', { name: /用 HDHive 获取资源|刷新 HDHive/ })).toBeVisible()
  })

  test('豆瓣详情页可以打开并展示匹配与资源网盘入口', async ({ page }) => {
    await page.goto('/douban/movie/1292052')
    await waitForPageReady(page)

    await expect(page.locator('.douban-detail-page h1.title')).toBeVisible()
    await expect(page.getByRole('button', { name: /匹配 TMDB|重新匹配 TMDB/ })).toBeVisible()
    await expect(page.getByRole('tab', { name: '115网盘' })).toBeVisible()
    await expect(page.getByRole('button', { name: /用 Nullbr 获取资源|刷新 Nullbr/ })).toBeVisible()

    await page.getByRole('tab', { name: 'HDHive' }).click()
    await expect(page.getByRole('button', { name: /用 HDHive 获取资源|刷新 HDHive/ })).toBeVisible()
  })
})
