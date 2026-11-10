"""Diagnostic reference similarity on the overlapping native timeline."""
import math


def compare_videos(generated, reference, count=16, size=256):
    import av
    import cv2
    import numpy as np

    def decode(path):
        frames, times = [], []
        with av.open(str(path)) as container:
            for frame in container.decode(video=0):
                if frame.time is None:
                    raise ValueError('Pixel comparison requires timestamps')
                t = float(frame.time)
                if times and t <= times[-1]:
                    raise ValueError('Nonmonotonic frame timestamp')
                times.append(t)
                frames.append(frame.to_ndarray(format='rgb24'))
        if len(frames) < 2:
            raise ValueError('Too few video frames')
        times = np.asarray(times) - times[0]
        return frames, times

    generated_frames, generated_times = decode(generated)
    reference_frames, reference_times = decode(reference)
    overlap = min(generated_times[-1], reference_times[-1])
    if overlap <= 0:
        raise ValueError('No positive overlapping timeline')
    stamps = np.linspace(0, overlap, count)

    def align(frames, times):
        indices = [int(np.argmin(np.abs(times - t))) for t in stamps]
        return np.stack([cv2.resize(frames[i], (size, size), interpolation=cv2.INTER_AREA) for i in indices])

    pred, truth = align(generated_frames, generated_times), align(reference_frames, reference_times)
    mse = float(np.mean(((pred.astype(np.float64) - truth.astype(np.float64)) / 255) ** 2))
    # Finite cap is recorded explicitly and never presented as infinite PSNR.
    psnr = 99.0 if mse <= 1e-12 else 10 * math.log10(1 / mse)
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    values = []
    for p, t in zip(pred.astype(np.float64), truth.astype(np.float64)):
        mu_p, mu_t = cv2.GaussianBlur(p, (11, 11), 1.5), cv2.GaussianBlur(t, (11, 11), 1.5)
        var_p = cv2.GaussianBlur(p * p, (11, 11), 1.5) - mu_p ** 2
        var_t = cv2.GaussianBlur(t * t, (11, 11), 1.5) - mu_t ** 2
        cov = cv2.GaussianBlur(p * t, (11, 11), 1.5) - mu_p * mu_t
        values.append(float(np.mean(((2 * mu_p * mu_t + c1) * (2 * cov + c2)) /
                                    ((mu_p ** 2 + mu_t ** 2 + c1) * (var_p + var_t + c2)))))
    return {'mse': mse, 'psnr': psnr, 'ssim': float(np.mean(values)), 'sampled_times_s': stamps.tolist(),
            'overlap_s': float(overlap), 'resize': [size, size], 'frames': count,
            'psnr_cap_db': 99.0, 'benchmark': 'geoflip-reference-diagnostic'}
