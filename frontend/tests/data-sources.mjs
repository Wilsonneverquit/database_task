import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { chromium } from 'playwright'

const base = process.env.TEST_BASE_URL || 'http://127.0.0.1:5000'
const passwords = JSON.parse(readFileSync(new URL('../../.runtime/public-logins.json',import.meta.url),'utf8'))
const executablePath = process.env.CHROME_PATH || [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
].find(existsSync)
const browser = await chromium.launch({headless:true,...(executablePath ? {executablePath} : {})})
try {
  const page = await browser.newPage()
  const errors = []
  page.on('pageerror',e=>errors.push(e.message))
  page.on('response',r=>{ if(r.url().includes('/api/') && r.status()>=500) errors.push(r.url()) })
  for (const source of ['real','demo']) {
    await page.goto(base+'/login?source='+source)
    await page.getByLabel('用户名').fill('analyst1')
    await page.getByLabel('口令',{exact:true}).fill(source==='real' ? passwords.analyst1 : '123456')
    const reply = page.waitForResponse(r=>r.url().endsWith('/api/login'))
    await page.getByRole('button',{name:'登录',exact:true}).click()
    const response = await reply
    assert.equal(response.status(),200)
    assert.equal(response.headers()['x-data-source'],source)
    await page.getByRole('heading',{name:'研判工作台',exact:true}).waitFor()
    if (source==='real') {
      await page.getByRole('link',{name:'查看公开数据'}).click()
      await page.getByText('数据来源与清洗记录',{exact:true}).click()
      await page.getByText(/Food Standards Agency/).waitFor()
      await page.goto(base+'/risk-map')
      await page.getByRole('heading',{name:'区域逐小时风险分布'}).waitFor()
    } else {
      await page.locator('.work-queue button').first().waitFor()
    }
  }
  await page.goto(base+'/?source=real')
  await page.getByRole('link',{name:'查看公开数据'}).waitFor()
  assert.deepEqual(errors,[])
  console.log('Public login, provenance, empty risk map, demo login and independent sessions passed.')
} finally {
  await browser.close()
}
