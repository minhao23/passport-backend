export function passportPhotoFilename(country: string): string {
  return `passport-${country.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.jpg`;
}

export function downloadPassportPhoto(url: string, country: string): void {
  const link = document.createElement("a");
  link.href = url;
  link.download = passportPhotoFilename(country);
  link.hidden = true;
  try {
    document.body.appendChild(link);
    link.click();
  } catch {
    // A blocked automatic download must not discard the photo or its manual link.
  } finally {
    link.remove();
  }
}
