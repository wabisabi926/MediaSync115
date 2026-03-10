async function waitForHttpOk(url, timeoutMs) {
  const startedAt = Date.now()
  let lastError = ''

  while (Date.now() - startedAt < timeoutMs) {
    try {
      const response = await fetch(url, { redirect: 'follow' })
      if (response.ok) return
      lastError = `HTTP ${response.status}`
    } catch (error) {
      lastError = String(error?.message || error || 'unknown error')
    }
    await new Promise((resolve) => setTimeout(resolve, 1000))
  }

  throw new Error(`service check failed for ${url}: ${lastError}`)
}

export default async function globalSetup(config) {
  const frontendBaseUrl = config.metadata?.frontendBaseUrl || 'http://127.0.0.1:5173'
  const backendHealthUrl = config.metadata?.backendHealthUrl || 'http://127.0.0.1:8000/health'
  await waitForHttpOk(backendHealthUrl, 30_000)
  await waitForHttpOk(frontendBaseUrl, 30_000)
}
