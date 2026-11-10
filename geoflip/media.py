"""Read presentation timestamps; never pad, retime, or freeze submitted videos."""
from io import BytesIO
import base64
import math


def inspect_video(path):
    import av
    times = []
    with av.open(str(path)) as container:
        videos = [s for s in container.streams if s.type == 'video']
        if len(videos) != 1:
            raise ValueError('Expected one video stream')
        for frame in container.decode(videos[0]):
            if frame.time is None:
                raise ValueError('Missing presentation timestamp')
            stamp = float(frame.time)
            if not math.isfinite(stamp) or (times and stamp <= times[-1]):
                raise ValueError('Invalid presentation timestamps')
            times.append(stamp)
    if len(times) < 2:
        raise ValueError('Too few decodable frames')
    return {'decoded_frames': len(times), 'first_timestamp_s': times[0],
            'last_timestamp_s': times[-1] - times[0],
            'timestamps_s': [t - times[0] for t in times]}


def sample_video(path, count=8, window=119/30):
    import av
    from PIL import ImageOps
    if count < 2 or window <= 0:
        raise ValueError('Invalid sampling configuration')
    info = inspect_video(path)
    times = info.pop('timestamps_s')
    prefix = [i for i, t in enumerate(times) if t <= window + 0.001]
    if len(prefix) < 2:
        raise ValueError('Too few frames in the observation prefix')
    indices = sorted({prefix[round(i * (len(prefix) - 1) / (count - 1))] for i in range(count)})
    wanted, images = set(indices), []
    with av.open(str(path)) as container:
        for index, frame in enumerate(container.decode(video=0)):
            if index in wanted:
                images.append(ImageOps.contain(frame.to_image().convert('RGB'), (832, 480)))
            if index >= indices[-1]:
                break
    if len(images) != len(indices):
        raise ValueError('Second decode did not reproduce selected frames')
    info.update(sampled_frames=len(indices), sampled_times_s=[times[i] for i in indices],
                sampled_frame_indices=indices, resize='contain-832x480-no-crop', prefix_limit_s=window)
    return images, info


def image_url(image):
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii')
