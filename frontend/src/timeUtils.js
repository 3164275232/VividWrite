// Fixed Beijing time, independent of the participant's computer time zone.
export function beijingTimestamp(value = Date.now()) {
  const epoch = new Date(value).getTime();
  return new Date(epoch + 8 * 60 * 60 * 1000).toISOString().replace('Z', '+08:00');
}
