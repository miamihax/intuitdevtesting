import type { Settings } from '../types'

// All time fields from the backend ("HH:MM" shift/window/ETA strings) are
// always transmitted as 24-hour clock strings -- this only affects display,
// matching how distance_unit only converts total_distance_km for display.
export function formatTime(value: string, format: Settings['time_format']): string {
  if (format === '24h') return value
  const [hoursStr, minutesStr] = value.split(':')
  const hours = Number(hoursStr)
  const period = hours >= 12 ? 'PM' : 'AM'
  const twelveHour = hours % 12 === 0 ? 12 : hours % 12
  return `${twelveHour}:${minutesStr} ${period}`
}
