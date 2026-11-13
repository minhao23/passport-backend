class ProcessingCancelledError(Exception):
    """The caller disconnected; stop work without reporting a photo failure."""


class ProcessingError(Exception):
    """A public processing failure with a fixed response contract."""

    code = "INTERNAL_SERVER_ERROR"
    status_code = 500
    message = (
        "We couldn't create your photo because of a server problem. "
        "Please try again in a moment. You don't need to change your photo."
    )

    def __init__(self):
        super().__init__(self.message)


class InternalServerError(ProcessingError):
    """An unexpected failure; private details belong in server logs."""


class ServiceBusyError(ProcessingError):
    code = "SERVICE_BUSY"
    status_code = 503
    message = "The photo service is busy. Please wait a moment and try again."


class QueueWaitTimeoutError(ServiceBusyError):
    message = "Your photo waited too long for processing. Please try again in a moment."


class PhotoIssueError(ProcessingError, ValueError):
    code = "PHOTO_ISSUE"
    status_code = 422
    message = (
        "Try a clear, well-lit photo with your whole head and shoulders visible."
    )


class EmptyPhotoError(PhotoIssueError):
    message = "The uploaded photo is empty. Please choose another photo."


class UploadTooLargeError(PhotoIssueError):
    status_code = 413
    message = "Please upload one photo of 10 MB or smaller."


class UploadTimeoutError(PhotoIssueError):
    status_code = 408
    message = "The upload took too long. Check your connection and try again."


class ImageDimensionsError(PhotoIssueError):
    status_code = 413
    message = (
        "This photo's dimensions are too large. Use a photo of 20 megapixels "
        "or fewer, with neither side exceeding 10,000 pixels."
    )


class InvalidPhotoError(PhotoIssueError):
    message = (
        "We couldn't open this photo. Please upload a valid JPG, PNG, or WebP image."
    )


class InvalidImageTypeError(PhotoIssueError):
    status_code = 400
    message = "Please upload an image file, such as JPG, PNG, or WebP."


class PersonNotDetectedError(PhotoIssueError):
    code = "PERSON_NOT_DETECTED"
    message = (
        "We couldn't find a person in this photo. Upload a clear, front-facing "
        "photo with your whole head and shoulders visible."
    )


class LowConfidenceError(PhotoIssueError):
    message = (
        "We couldn't identify the subject clearly enough. Try a sharper, "
        "well-lit photo with your whole head and shoulders visible."
    )


class SubjectSeparationError(PhotoIssueError):
    message = (
        "We couldn't separate the subject from the background. Try a well-lit "
        "photo against a simple background."
    )


class SubjectTooSmallError(PhotoIssueError):
    message = (
        "The visible subject is too small to create a photo. Try a closer, clearer photo."
    )


class InvalidCountryError(ProcessingError, ValueError):
    code = "INVALID_COUNTRY"
    status_code = 400
    message = "Please select a supported country."
