import argparse
import torch
from torch.cuda import get_device_properties


# this is used globally until i clean this all up
args = None

def init():
    global args


    # Check for GPU and reduce the default image size if low VRAM
    default_image_size = 512  # >8GB VRAM
    if not torch.cuda.is_available():
        default_image_size = 256  # no GPU found
    elif get_device_properties(0).total_memory <= 2 ** 33:  # 2 ** 33 = 8,589,934,592 bytes = 8 GB
        default_image_size = 318  # <8GB VRAM

    # Create the parser
    vq_parser = argparse.ArgumentParser(description='Image generation using VQGAN+CLIP')

    # Add the arguments
    vq_parser.add_argument("-p",    "--prompts", type=str, help="Text prompts", default=None, dest='prompts')
    vq_parser.add_argument("-ip",   "--image_prompts", type=str, help="Image prompts / target image", default=[], dest='image_prompts')
    vq_parser.add_argument("-i",    "--iterations", type=int, help="Number of iterations", default=500, dest='max_iterations')
    vq_parser.add_argument("-se",   "--save_every", type=int, help="Save image iterations", default=50, dest='save_freq')
    vq_parser.add_argument("-sb",   "--save_best", help="Save the best scored image", action='store_true', dest='save_best')
    vq_parser.add_argument("-stats","--stats_every", type=int, help="stats display frequency", default=50, dest='display_freq')
    vq_parser.add_argument("-s",    "--size", nargs=2, type=int, help="Image size (width height) (default: %(default)s)", default=[default_image_size,default_image_size], dest='size')
    vq_parser.add_argument("-ii",   "--init_image", type=str, help="Initial image", default=None, dest='init_image')
    vq_parser.add_argument("-in",   "--init_noise", type=str, help="Initial noise image (pixels or gradient)", default=None, dest='init_noise')
    vq_parser.add_argument("-iw",   "--init_weight", type=float, help="Initial weight", default=0., dest='init_weight')
    vq_parser.add_argument("-m",    "--clip_model", type=str, help="CLIP model (e.g. ViT-B/32, ViT-B/16)", default='ViT-B/32', dest='clip_model')
    vq_parser.add_argument("-conf", "--vqgan_config", type=str, help="VQGAN config", default=f'checkpoints/vqgan_imagenet_f16_16384.yaml', dest='vqgan_config')
    vq_parser.add_argument("-ckpt", "--vqgan_checkpoint", type=str, help="VQGAN checkpoint", default=f'checkpoints/vqgan_imagenet_f16_16384.ckpt', dest='vqgan_checkpoint')
    vq_parser.add_argument("-nps",  "--noise_prompt_seeds", nargs="*", type=int, help="Noise prompt seeds", default=[], dest='noise_prompt_seeds')
    vq_parser.add_argument("-npw",  "--noise_prompt_weights", nargs="*", type=float, help="Noise prompt weights", default=[], dest='noise_prompt_weights')
    vq_parser.add_argument("-lr",   "--learning_rate", type=float, help="Learning rate", default=0.1, dest='step_size')
    vq_parser.add_argument("-cutm", "--cut_method", type=str, help="Cut method", choices=['original','updated','nrupdated','updatedpooling','latest'], default='latest', dest='cut_method')
    vq_parser.add_argument("-cuts", "--num_cuts", type=int, help="Number of cuts", default=32, dest='cutn')
    vq_parser.add_argument("-cutp", "--cut_power", type=float, help="Cut power", default=1., dest='cut_pow')
    vq_parser.add_argument("-sd",   "--seed", type=int, help="Seed", default=None, dest='seed')
    vq_parser.add_argument("-opt",  "--optimiser", type=str, help="Optimiser", choices=['Adam','AdamW','Adagrad','Adamax','DiffGrad','AdamP','RAdam','RMSprop','MADGRAD'], default='Adam', dest='optimiser')
    vq_parser.add_argument("-o",    "--output", type=str, help="Output filename", default="output.png", dest='output')
    vq_parser.add_argument("-vid",  "--video", action='store_true', help="Create video frames?", dest='make_video')
    vq_parser.add_argument("-zvid", "--zoom_video", action='store_true', help="Create zoom video?", dest='make_zoom_video')
    vq_parser.add_argument("-zs",   "--zoom_start", type=int, help="Zoom start iteration", default=0, dest='zoom_start')
    vq_parser.add_argument("-zse",  "--zoom_save_every", type=int, help="Save zoom image iterations", default=10, dest='zoom_frequency')
    vq_parser.add_argument("-zsc",  "--zoom_scale", type=float, help="Zoom scale %", default=0.99, dest='zoom_scale')
    vq_parser.add_argument("-zsx",  "--zoom_shift_x", type=int, help="Zoom shift x (left/right) amount in pixels", default=0, dest='zoom_shift_x')
    vq_parser.add_argument("-zsy",  "--zoom_shift_y", type=int, help="Zoom shift y (up/down) amount in pixels", default=0, dest='zoom_shift_y')
    vq_parser.add_argument("-cpe",  "--change_prompt_every", type=int, help="Prompt change frequency", default=0, dest='prompt_frequency')
    vq_parser.add_argument("-vl",   "--video_length", type=float, help="Video length in seconds (not interpolated)", default=10, dest='video_length')
    vq_parser.add_argument("-ofps", "--output_video_fps", type=float, help="Create an interpolated video (Nvidia GPU only) with this fps (min 10. best set to 30 or 60)", default=0, dest='output_video_fps')
    vq_parser.add_argument("-ifps", "--input_video_fps", type=float, help="When creating an interpolated video, use this as the input fps to interpolate from (>0 & <ofps)", default=15, dest='input_video_fps')
    vq_parser.add_argument("-d",    "--deterministic", action='store_true', help="Enable cudnn.deterministic?", dest='cudnn_determinism')
    vq_parser.add_argument("-aug",  "--augments", nargs='+', action='append', type=str, choices=['Ji','Sh','Gn','Pe','Ro','Af','Et','Ts','Cr','Er','Re'], help="Enabled augments (latest vut method only)", default=[], dest='augments')
    vq_parser.add_argument("-vsd",  "--video_style_dir", type=str, help="Directory with video frames to style", default=None, dest='video_style_dir')
    vq_parser.add_argument("-cd",   "--cuda_device", type=str, help="Cuda device to use", default="cuda:0", dest='cuda_device')

    # attempt to use mixed precision mode here
    # need to hunt down causes of the decoder produces inf's/nan's. current hack is to replace them with min/max floats, slower and produces poorer results than 32 bit.
    vq_parser.add_argument("-usemix", "--use_mixed",  action='store_true', help="mixed precision reduces memory size greatly, and gave me 50% more pixels, but seemingly at the cost of numeric instability and not quite as good results. Augmentations do not work in this mode, yet", 
                            dest='use_mixed_precision')

    # this works, can go from 400x400 to 575x400 on an 8GB card being used as a display device
    # time to crunch went up from 1.07 per iter to 7.5s per iteration, cant be used in conjunction with mixed precision mode ( yet )
    vq_parser.add_argument("-clipcpu",   "--clip_cpu",  action='store_true', help="forces the clip model into the cpu. slows things down but frees up memory so you can make larger images on low VRAM cards", 
                            dest='clip_cpu')

    # helpful for tracking down various floating poitn errors 
    vq_parser.add_argument("-ac",   "--anomalyChecker",  action='store_true', help="enabled the pyTorch anomaly checker for nan's, useful in mixed precision mode which has had some issues", 
                            dest='anomaly_checker')

    # simple memory logger
    vq_parser.add_argument("-lm",   "--logMem",  action='store_true', help="log memory usage every checkin", dest='log_mem')

    # writes one shot clip and a sort of prompt stat check using clip
    vq_parser.add_argument("-lcp",   "--logClipProbabilities",  action='store_true', dest='log_clip')
    vq_parser.add_argument("-lcos",  "--logClipOneShotGuesses",  action='store_true', dest='log_clip_oneshot')

    # Execute the parse_args() method
    args = vq_parser.parse_args()