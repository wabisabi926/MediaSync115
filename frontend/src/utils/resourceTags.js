/**
 * Extract resolution and format tags from resource metadata.
 */

const RESOLUTION_PATTERNS = [
  { label: '4K', pattern: /\b(?:4K|2160[pPiI]|UHD)\b/i },
  { label: '1080p', pattern: /\b(?:1080[pPiI]|FHD|Full\s*HD)\b/i },
  { label: '720p', pattern: /\b720[pPiI]\b/i },
  { label: '480p', pattern: /\b480[pPiI]\b/i },
]

const FORMAT_PATTERNS = [
  { label: 'Dolby Vision', pattern: /\b(?:Dolby\s*Vision|DoVi|DV)\b/i },
  { label: 'HDR10+', pattern: /\bHDR10\+/i },
  { label: 'HDR10', pattern: /\bHDR10\b/i },
  { label: 'HDR', pattern: /\bHDR\b/i },
  { label: 'SDR', pattern: /\bSDR\b/i },
  { label: 'REMUX', pattern: /\bREMUX\b/i },
  { label: 'BluRay', pattern: /\b(?:Blu[-\s]?Ray|BDRip|BDRemux|BD)\b/i },
  { label: 'WEB-DL', pattern: /\b(?:WEB[-\s]?DL|WEBDL|WEBRip|WEB)\b/i },
  { label: 'HEVC', pattern: /\b(?:HEVC|[Hh]\.?265|x265)\b/ },
  { label: 'H.264', pattern: /\b(?:AVC|[Hh]\.?264|x264)\b/ },
  { label: 'Atmos', pattern: /\bAtmos\b/i },
  { label: 'DTS-HD', pattern: /\bDTS[-\s]?HD(?:\s*MA)?\b/i },
  { label: 'TrueHD', pattern: /\bTrueHD\b/i },
  { label: 'DTS', pattern: /\bDTS\b/i },
  { label: 'AAC', pattern: /\bAAC\b/i },
  { label: 'FLAC', pattern: /\bFLAC\b/i },
]

export const ALL_RESOLUTIONS = RESOLUTION_PATTERNS.map(p => p.label)
export const ALL_FORMATS = FORMAT_PATTERNS.map(p => p.label)

function collectText(resource) {
  const parts = []
  for (const key of ['resource_name', 'title', 'name', 'overview']) {
    const val = resource[key]
    if (typeof val === 'string' && val.trim()) parts.push(val)
  }
  for (const key of ['quality', 'resolution']) {
    const val = resource[key]
    if (Array.isArray(val)) parts.push(...val.filter(Boolean).map(String))
    else if (typeof val === 'string' && val.trim()) parts.push(val)
  }
  return parts.join(' ')
}

export function extractTags(resource) {
  const text = collectText(resource)

  let resolution = ''
  for (const { label, pattern } of RESOLUTION_PATTERNS) {
    if (pattern.test(text)) { resolution = label; break }
  }

  const formats = []
  const seen = new Set()
  for (const { label, pattern } of FORMAT_PATTERNS) {
    if (seen.has(label)) continue
    if (pattern.test(text)) {
      formats.push(label)
      seen.add(label)
      if (label === 'HDR10+' || label === 'HDR10') seen.add('HDR')
      if (label === 'DTS-HD') seen.add('DTS')
    }
  }

  return { resolution, formats }
}
