import cv2
import matplotlib.pyplot as plt
import numpy as np
import scipy.misc
import random
import os
from scipy.ndimage import rotate
from scipy.stats import bernoulli

# CSV column names
COLUMNS = ['center','left','right','steering','throttle','brake','speed']

# Image cropping delimiters
HORIZON=60
BONNET=136
# Parameters to calculate the steering correction when taking left/right cameras
# https://medium.com/@ksakmann/behavioral-cloning-make-a-car-drive-like-yourself-dc6021152713#.fc0drgwk7
offset=1.0
dist=15.0
STEERING_COEFFICIENT = offset/dist * 360/( 2*np.pi)  / 25.0

def random_flip(image, steering_angle, flipping_prob=0.5):
    """
    Randomly flip an image, with a given probability
    """
    if random.random() < flipping_prob:
        return np.fliplr(image), -1 * steering_angle
    else:
        return image, steering_angle

def random_shadows(image):
    """
    Generate a random shadow on the image
    area parameter is a percentage of the total image area
    """
    # Generate a separate buffer
    shadows = image.copy()

    image_area = shadows.shape[0] * shadows.shape[1]
    poly = get_shadow_poly(shadows.shape[0], shadows.shape[1])
    cv2.fillPoly(shadows, np.array([poly]), -1)

    alpha = np.random.uniform(0.6, 0.9)
    return cv2.addWeighted(shadows, alpha, image, 1-alpha,0,image)

def get_shadow_poly(max_x, max_y):
    """
    Get the polygons of a random area delimited between
    max_x, max_y. The polygons generated will either be horizontal
    or vertically aligned with the image, with a random distribution.
    """
    horizontal = np.random.uniform()

    if horizontal < 0.5:
        x1 = random.randint(0, max_x/2)
        y1 = 0
        x2 = random.randint(max_x / 2, max_x)
        y2 = 0
        x3 = random.randint(max_x / 2, max_x)
        y3 = max_y
        x4 = random.randint(0, max_x/2)
        y4 = max_y
    else:
        x1 = 0
        y1 = random.randint(0, max_y/2)
        x2 = 0
        y2 = random.randint(max_y / 2, max_y)
        x3 = max_x
        y3 = random.randint(max_y / 2, max_y)
        x4 = max_x
        y4 = random.randint(0, max_y/2)

    return [[x1,y1],[x2,y2],[x3,y3], [x4,y4]]

def random_shear(image, steering_angle, shear_range=200):
    """
    Sources:
    https://medium.com/@ksakmann/behavioral-cloning-make-a-car-drive-like-yourself-dc6021152713#.7k8vfppvk
    https://github.com/ksakmann/CarND-BehavioralCloning/blob/master/model.py
    """
    rows, cols, ch = image.shape
    dx = np.random.randint(-shear_range, shear_range + 1)
    random_point = [cols / 2 + dx, rows / 2]
    pts1 = np.float32([[0, rows], [cols, rows], [cols / 2, rows / 2]])
    pts2 = np.float32([[0, rows], [cols, rows], random_point])
    dsteering = dx / (rows / 2) * 360 / (2 * np.pi * 25.0) / 6.0
    M = cv2.getAffineTransform(pts1, pts2)
    image = cv2.warpAffine(image, M, (cols, rows), borderMode=1)
    steering_angle += dsteering

    return image, steering_angle

def crop(image):
    """
    Crop the image between the given delimiters for the
    horizon and the bonnet of the car.
    """
    shape = image.shape

    cropped = image[HORIZON:BONNET,0:shape[1],:]

    return cropped

def resize(image, resize_dim):
    return cv2.resize(image,resize_dim,cv2.INTER_AREA)

def random_brightness(image, median=0.8, dev=0.4):
    """
    Source: http://stackoverflow.com/questions/32609098/how-to-fast-change-image-brightness-with-python-opencv
    """
    hsv = cv2.cvtColor(image,cv2.COLOR_RGB2HSV)
    random_bright = median + dev * np.random.uniform(-1.0, 1.0)
    hsv[:,:,2] = hsv[:,:,2]*random_bright

    rgb = cv2.cvtColor(hsv,cv2.COLOR_HSV2RGB)
    return rgb

def generate_new_image(image, steering_angle, do_shear_prob=0.5):
    """
    :param image: the image to augment.
    :param steering_angle: the steering label for this image, will be adjusted accordingly to the augmentation steps taken
    :param do_shear_prob: the probability of performing a random shear transformation on the image
    :return: the augmented image and steering angle
    """

    if random.random() < do_shear_prob:
        image, steering_angle = random_shear(image, steering_angle)

    return image, steering_angle

# center,left,right,steering,throttle,brake,speed
def get_random_camera_data(csv, index):
    """
    Get one of the left, center or right images together with
    the corresponding(adjusted) steering angle.
    """
    rnd = np.random.randint(0, 3)
    img = csv.iloc[index][COLUMNS.index('center') + rnd].strip()
    angle = csv.iloc[index][COLUMNS.index('steering')]

    # Adjust steering based on camera position
    if rnd == COLUMNS.index('left'):
        angle = angle + STEERING_COEFFICIENT
    elif rnd == COLUMNS.index('right'):
        angle = angle - STEERING_COEFFICIENT

    return (img, angle)

def next_batch(samples, batch_size=64):
    """
    Get a random batch of data rows
    """
    random_rows = np.random.randint(0, len(samples), batch_size)

    batch = []
    for index in random_rows:
        data = get_random_camera_data(samples, index)
        batch.append(data)

    return batch

def generate_next_batch(samples, batch_size=64, augment=True):
    """
    Generator for image, steering angle batches.
    :param samples: set of training samples, as read from the .csv files
    :param resize_dim: images will be resized to these dimensions
    :param batch_size: the size of the batches the generator returns.
    """
    while True:
        X_batch = []
        y_batch = []
        images = next_batch(samples, batch_size)
        for img_file, angle in images:
            image = plt.imread(img_file)
            if augment:
                image, angle = generate_new_image(image, angle)
            else:
                image = crop(image)
                image = resize(image, resize_dim)
            X_batch.append(image)
            y_batch.append(angle)

        yield np.array(X_batch), np.array(y_batch)