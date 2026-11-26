export function passportPhotoFilename(country: string): string {
  return `passport-${country.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.jpg`;
}
