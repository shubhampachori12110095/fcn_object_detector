#!/usr/bin/env python

import os
import caffe
import random
import time
import numpy as np
import cv2 as cv
import argumentation_engine as ae

"""
Class for bounding box detection
"""
class DataArgumentationLayer(caffe.Layer):

    def setup(self, bottom, top):
        #! check that inputs are pair of image and labels (bbox and label:int)
        if len(bottom) > 0:
            raise Exception('This layer takes no bottom')
        
        if len(top) < 6:
            raise Exception('Current Implementation needs 6 top blobs')

        try:
            plist = self.param_str.split(',')
            self.image_size_x = int(plist[0])
            self.image_size_y = int(plist[1])
            self.stride = int(plist[2])
            self.num_classes = int(plist[3])
            
            self.batch_size = int(plist[4])
            self.train_fn = str(plist[5]) #! dataset textfile
            #self.randomize = bool(plist[6])
            self.randomize = True

            if not os.path.isfile(self.train_fn):
                raise ValueError('Provide the dataset textfile')

            else:
                # self.img_paths, self.rects, self.labels = self.read_and_decode_lines()
                self.img_paths, self.mask_imgs, self.labels, self.rects = self.read_data_from_textfile2()
                self.idx = 0 #! start index

            self.__gen_ae = ae.ArgumentationEngineMapping(self.img_paths, self.mask_imgs, \
                                                          self.labels, self.rects, \
                                                          self.image_size_x, self.image_size_y, True)
            self.__ae = ae.ArgumentationEngine(self.image_size_x, self.image_size_y, \
                                               self.stride, self.num_classes)

            if self.randomize:
                random.seed()
                self.idx = random.randint(0, (len(self.img_paths))-1)
            
        except ValueError:
            raise ValueError('Parameter string missing or data type is wrong!')
            
    def reshape(self, bottom, top):
        #! check input dimensions
        n_images = self.batch_size
        out_size_x = int(self.image_size_x / self.stride)
        out_size_y = int(self.image_size_y / self.stride)

        channel_stride = 4
        channels = int(self.num_classes * channel_stride)
        
        top[0].reshape(n_images, 3, self.image_size_y, self.image_size_x)
        top[1].reshape(n_images, 1, self.image_size_y, self.image_size_x) #! cvg labels  # 1
        # top[1].reshape(n_images, self.num_classes, out_size_y, out_size_x) #! cvg labels  # 1
        top[2].reshape(n_images, channels, out_size_y, out_size_x) #! bbox labels # 4
        top[3].reshape(n_images, channels, out_size_y, out_size_x) #! size labels # 4
        top[4].reshape(n_images, channels, out_size_y, out_size_x) #! obj labels  # 4
        top[5].reshape(n_images, channels, out_size_y, out_size_x) #! cvg block   # 4
        

    def forward(self, bottom, top):
        use_mapping = True
        for index in xrange(0, self.batch_size, 1):
            img = cv.imread(self.img_paths[self.idx])
            rects = self.rects[self.idx]
            labels = self.labels[self.idx]
            im_mask = None
            if use_mapping:
                rects = []
                labels = []
                
                im_rgb = cv.imread('/home/krishneel/Desktop/frame0000.jpg')
                w = im_rgb.shape[1] / 2
                h = im_rgb.shape[0] / 2
                x = random.randint(0, w)
                y = random.randint(0, h)
                x = x - (x+w - im_rgb.shape[1]) if x+w > im_rgb.shape[1] else x
                y = y - (y+h - im_rgb.shape[0]) if y+h > im_rgb.shape[0] else y
                im_rgb = im_rgb[y:y+h, x:x+w]
                
                im_mask = cv.imread(self.mask_imgs[self.idx])
                im_rgb = cv.resize(im_rgb, (im_mask.shape[1], im_mask.shape[0]))

                num_proposals = random.randint(1, 3)
                img, im_mask, rects, labels = self.__gen_ae.process(num_proposals, im_rgb)
                
            img, rects, label_map = self.__ae.random_argumentation(img, rects, im_mask)
            img, rects = self.__ae.resize_image_and_labels(img, rects)            
            foreground_labels, boxes_labels, size_labels, obj_labels, coverage_label = \
            self.__ae.bounding_box_parameterized_labels(img, rects, labels)
            
            top[0].data[index] = img.transpose((2, 0, 1))
            # top[1].data[index] = foreground_labels.copy()
            top[2].data[index] = boxes_labels.copy()
            top[3].data[index] = size_labels.copy()
            top[4].data[index] = obj_labels.copy()
            top[5].data[index] = coverage_label.copy()

            ##! create mask
            mask = cv. resize(label_map[:, :, 0].copy(), (self.image_size_x, self.image_size_y), \
                              interpolation = cv.INTER_NEAREST)
            
            label_datum = np.zeros((self.image_size_x, self.image_size_y, 1), np.uint8)
            label_datum[:, :, 0] = mask.copy()
            label_datum = label_datum.transpose((2, 0, 1))
            
            top[1].data[index] = label_datum.copy()
            # end mask
            
            self.idx = random.randint(0, (len(self.img_paths))-1)

    def backward(self, top, propagate_down, bottom):
        pass
        

    """
    Function to read and extract path to images, bounding boxes and the labels
    """
    def read_and_decode_lines(self):
        lines = [line.rstrip('\n')
                 for line in open(self.train_fn)
        ]
        
        if self.randomize:
            np.random.shuffle(lines)

        img_paths = []
        rects = []
        labels = []
        for line in lines:
            line_val = line.split()
            img_paths.append(line_val[0])
            rect = []
            for i in xrange(1, len(line_val)-1, 1):
                rect.append(int(line_val[i]))
            rect = np.array([rect])
            rects.append(rect)
            
            label = int(line_val[-1]) - 1 ##> change to auto rank
            label = np.array([label])
            labels.append(label)
        return np.array(img_paths), np.array(rects), np.array(labels)

    def read_data_from_textfile2(self):
        lines = [line.rstrip('\n')
                 for line in open(self.train_fn)
        ]
        img_paths = []
        mask_imgs = []
        labels = []
        rects = []
        for index in xrange(0, len(lines), 2):
            img_paths.append(lines[index].split()[0])
            mask_imgs.append(lines[index].split()[1])
            labels.append(int(lines[index].split()[2]))
            x = int(float(lines[index].split()[3]))
            y = int(float(lines[index].split()[4]))
            w = int(float(lines[index].split()[5]))
            h = int(float(lines[index].split()[6]))
            rects.append(np.array([x, y, w, h], dtype=np.int))
             
        ##! create unique labels
        labels = np.array(labels)
        label_unique, label_indices = np.unique(labels, return_index=False, \
                                                return_inverse=True, return_counts=False)

        #! create new label manifest
        manifest_fn = 'snapshots/labels/labels_' + time.strftime("%Y%m%d%H%M%S") + '.txt'
        text_file = open(str(manifest_fn), 'w')
        for index, label in enumerate(label_unique):
            n_label = index + 1
            a = str(n_label) + ' ' +str(label)
            text_file.write('%s\n'% a)
        text_file.close()
        
        return np.array(img_paths), np.array(mask_imgs), label_indices, np.array(rects)


        
"""
Class for semantic segmentation based detection
"""
class DataArgumentationLayerFCN(caffe.Layer):

    def setup(self, bottom, top):
        #! check that inputs are pair of image and labels (bbox and label:int)
        if len(bottom) > 0:
            raise Exception('This layer takes no bottom')
        
        if len(top) < 2:
            raise Exception('Current Implementation needs 2 top blobs')

        try:
            plist = self.param_str.split(',')
            params = eval(self.param_str)
            self.batch_size = int(params['batch_size'])
            self.image_size_x = int(params['im_width'])
            self.image_size_y = int(params['im_height'])
            self.train_fn = str(params['filename'])
            self.randomize = bool(params.get('randomize', True))
            self.var_scale = bool(params.get('var_scale', False))
            
            if not os.path.isfile(self.train_fn):
                raise ValueError('Provide the dataset textfile')
            else:
                # self.img_paths, self.mask_imgs, self.labels = self.read_data_from_textfile()
                self.img_paths, self.mask_imgs, self.labels, self.rects = \
                self.read_data_from_textfile2()

                if self.img_paths.shape != self.mask_imgs.shape or \
                   self.img_paths.shape != self.labels.shape:
                    raise Exception('label and image size are not equal')
                
                self.idx = 0 #! start index

            # self.__ae = ae.ArgumentationEngineFCN(self.image_size_x, self.image_size_y)
            self.__ae = ae.ArgumentationEngineMapping(self.img_paths, self.mask_imgs, \
                                                      self.labels, self.rects, \
                                                      self.image_size_x, self.image_size_y)
            if self.randomize:
                random.seed()
                self.idx = random.randint(0, (len(self.img_paths))-1)
            
        except ValueError:
            raise ValueError('Parameter string missing or data type is wrong!')
            
    def reshape(self, bottom, top):
        #! check input dimensions
        n_images = self.batch_size
        top[0].reshape(n_images, 3, self.image_size_y, self.image_size_x)
        top[1].reshape(n_images, 1, self.image_size_y, self.image_size_x)

    def forward(self, bottom, top):
        """
        for index in xrange(0, self.batch_size, 1):
            im_rgb = cv.imread(self.img_paths[self.idx])
            im_mask = cv.imread(self.mask_imgs[self.idx])
            label = self.labels[self.idx]
            rgb_datum, label_datum = self.__ae.process2(im_rgb, im_mask, label)

            if len(label_datum.shape) < 3:
                while len(template_datum.shape) < 3:
                    self.idx = random.randint(0, len(self.img_paths)-1)
                    im_rgb = cv.imread(self.img_paths[self.idx])
                    im_mask = cv.imread(self.mask_imgs[self.idx])

                    rgb_datum, label_datum = self.__ae.process2(im_rgb, im_mask, label)

            top[0].data[index] = rgb_datum.copy()
            top[1].data[index] = label_datum.copy()
            self.idx = random.randint(0, len(self.img_paths)-1)
        """
        
        for index in xrange(0, self.batch_size, 1):
            im_rgb = cv.imread(self.img_paths[self.idx])
            im_mask = cv.imread(self.mask_imgs[self.idx])
            label = self.labels[self.idx]
            rect = self.rects[self.idx]
           
            im_rgb = cv.imread('/home/krishneel/Desktop/frame0000.jpg')
            w = im_rgb.shape[1] / 2
            h = im_rgb.shape[0] / 2
            x = random.randint(0, w)
            y = random.randint(0, h)
            x = x - (x+w - im_rgb.shape[1]) if x+w > im_rgb.shape[1] else x
            y = y - (y+h - im_rgb.shape[0]) if y+h > im_rgb.shape[0] else y
            im_rgb = im_rgb[y:y+h, x:x+w]
            im_rgb = cv.resize(im_rgb, (im_mask.shape[1], im_mask.shape[0]))

            #cv.imshow('img', im_rgb)
            #cv.waitKey(0)

            num_proposals = random.randint(1, 3)
            rgb_datum, label_datum = self.__ae.process(num_proposals, im_rgb) #, im_mask, rect)
            
            # if len(label_datum.shape) < 3:
            #     while len(label_datum.shape) < 3:
            #         self.idx = random.randint(0, len(self.img_paths)-1)
            #         im_rgb = cv.imread(self.img_paths[self.idx])
            #         im_mask = cv.imread(self.mask_imgs[self.idx])
            #         label = self.labels[self.idx]
            #         rect = self.rects[self.idx]
            #         rgb_datum, label_datum = self.__ae.process(num_proposals, im_rgb) #, im_mask, rect)

            top[0].data[index] = rgb_datum.copy()
            top[1].data[index] = label_datum.copy()
            self.idx = random.randint(0, len(self.img_paths)-1)

    def backward(self, top, propagate_down, bottom):
        pass
        
    def read_data_from_textfile(self):
        lines = [line.rstrip('\n')
                 for line in open(self.train_fn)
        ]
        img_paths = []
        mask_imgs = []
        labels = []
        for index in xrange(0, len(lines), 2):
            img_paths.append(lines[index].split()[0])
            mask_imgs.append(lines[index+1].split()[0])
            labels.append(lines[index+1].split()[1])

        ##! create unique labels
        labels = np.array(labels)
        label_unique, label_indices = np.unique(labels, return_index=False, \
                                                return_inverse=True, return_counts=False)
        #! shift to one indices
        label_indices += 1

        #! create new label manifest
        manifest_fn = 'snapshots/labels/labels_' + time.strftime("%Y%m%d%H%M%S") + '.txt'
        text_file = open(str(manifest_fn), 'w')
        for index, label in enumerate(label_unique):
            n_label = index + 1
            a = str(n_label) + ' ' +str(label)
            text_file.write('%s\n'% a)
        text_file.close()
        
        return np.array(img_paths), np.array(mask_imgs), label_indices

    def read_data_from_textfile2(self):
        lines = [line.rstrip('\n')
                 for line in open(self.train_fn)
        ]
        img_paths = []
        mask_imgs = []
        labels = []
        rects = []
        for index in xrange(0, len(lines), 2):
            img_paths.append(lines[index].split()[0])
            mask_imgs.append(lines[index].split()[1])
            labels.append(int(lines[index].split()[2]))
            x = int(float(lines[index].split()[3]))
            y = int(float(lines[index].split()[4]))
            w = int(float(lines[index].split()[5]))
            h = int(float(lines[index].split()[6]))
            rects.append(np.array([x, y, w, h], dtype=np.int))
             
        ##! create unique labels
        labels = np.array(labels)
        label_unique, label_indices = np.unique(labels, return_index=False, \
                                                return_inverse=True, return_counts=False)
        #! shift to one indices
        label_indices += 1

        #! create new label manifest
        manifest_fn = 'snapshots/labels/labels_' + time.strftime("%Y%m%d%H%M%S") + '.txt'
        text_file = open(str(manifest_fn), 'w')
        for index, label in enumerate(label_unique):
            n_label = index + 1
            a = str(n_label) + ' ' +str(label)
            text_file.write('%s\n'% a)
        text_file.close()
        
        return np.array(img_paths), np.array(mask_imgs), label_indices, np.array(rects)

        
"""
Test debugging layer
"""
class DataArgumentationTestLayer(caffe.Layer):

    def setup(self, bottom, top):
        pass
        
    def reshape(self, bottom, top):
        self.image_size_y = bottom[0].data.shape[2]
        self.image_size_x = bottom[0].data.shape[3]
        self.batch_size = bottom[0].data.shape[0]
    
    def forward(self, bottom, top):
        for i in xrange(0, self.batch_size, 1):
            image = bottom[0].data[i]
            image = image.transpose((1, 2, 0))
            
            # cv.namedWindow('timage', cv.WINDOW_NORMAL)
            # cv.imshow('timage', image)
            # cv.waitKey(3)

    def bottom(self, bottom, top):
        pass
