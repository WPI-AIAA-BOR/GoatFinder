import numpy as np
import time
import nav_loader
import threading
from LSM9DS0 import LSM9DS0

global nine_dof_lock
nine_dof_lock = threading.Lock()

global lsm
lsm = LSM9DS0()

class navsystem(object):
    
    def __init__(self, xy_frames_stored, # number of past x/y/theta readings to remember
            sensor_frames_stored, # number of past 9DOF readings to remember
            encoder_frames_stored, # number of past encoder readings to remember
            zero_angle, # offset for theta
            encoder_distance, # distance of one encoder tick
            skid_err_range, # how much faster the wheels can be than the accelerometers would estimate without the system reporting slippage, as a percentage of accelerometer readings
            accel_time_step, # time between acclerometer readings, required as a factor for the reimann sum to calculate velocity
            gyro_pitch_axis, # should be Y or 1 for PCB version
            gyro_gain = 0.00152717*2, # scales to radians
            gyro_mag_ratio = 1, # ratio mixing gyro and magnetometer angles
            mag_filter_rate = .9,
            gyro_filter_rate = .8
            
            ):

        self.mag_filter_rate = mag_filter_rate
        self.gyro_filter_rate = gyro_filter_rate
        self.gyro_unfiltered = 0
        self.gyro_zero = 0
        self.gyro_gain = gyro_gain
        self.x_n_1 = 0
        self.w_n_1 = 0
        self.heading_gyro = 0
        self.heading_mag = 0
        self.heading = 0
        self.gyro = np.zeros((3,sensor_frames_stored,), dtype = np.float32)
        self.gyro_mag_ratio = gyro_mag_ratio
        self.time = time.time()
        self.gyro_pitch_axis = gyro_pitch_axis
        self.accel_time_step = accel_time_step
        self.sensor_frames_stored = sensor_frames_stored
        self.zero_angle = zero_angle # offset for theta = 0
        # preallocate arrays
        #dx = np.zeros((1,xy_frames_stored), dtype = np.float32)
        #dy = np.zeros((1,xy_frames_stored), dtype = np.float32)
        #theta = np.zeros((1,xy_frames_stored), dtype = np.float32) # unneeded
        self.accel = np.zeros((3,sensor_frames_stored,), dtype = np.float32)
        heading_old = self.heading;
        self.mag = np.zeros((3,sensor_frames_stored,), dtype = np.float32)
        self.encoder = np.zeros((2,encoder_frames_stored,), dtype = np.float32)
        self.encoder_cnt = np.zeros(2, dtype = int)
        #r = np.zeros((1,xy_frames_stored), dtype = int)
        #xy_i = 0 # index into x/y/theta
        self.sensor_i = 0 # index into 9DOF arrays
        self.sensor_last_i = 0 # last index already read
        self.encoder_i = 0 # index into past encoders
        self.v_old = 0 # last measured velocity 
        #self.dt = 0.1 # 
        self.magx = [10000,0]
        self.magy = [10000,0]
        self.zero_gyro()

    def new_9dof(self,full_9dof):
        self.gyro[:,self.sensor_i] = full_9dof[0][:]
        self.mag[:,self.sensor_i] = full_9dof[1][:]
        self.accel[:,self.sensor_i] = full_9dof[2][:]
        self.sensor_i = (self.sensor_i + 1) % self.sensor_frames_stored

    def new_encoder(self,n): # n specifies left or right
        self.encoder_cnt[n] += 1

    def read_displacement(self):
        #calculate time since last read_displacement()
        time_old = self.time
        self.time = time.time()
        t = self.time-time_old
        
        

        #create list of new acceleration readings and number of time steps
        if (self.sensor_i > self.sensor_last_i): # if array has not looped around
            new_accels = self.accel[:, self.sensor_last_i+1:self.sensor_i]
            new_gyros = self.gyro[:, self.sensor_last_i+1:self.sensor_i]
            n = self.sensor_i - self.sensor_last_i

        else: # if array has looped around
            new_accels = np.hstack((              # concatenate...
                    self.accel[:, self.sensor_last_i:], # last to end and ...
                    self.accel[:, :self.sensor_i]))      # begininning to current
            new_gyros = np.hstack((              # concatenate...
                    self.gyro[:, self.sensor_last_i:], # last to end and ...
                    self.gyro[:, :self.sensor_i]))      # begininning to current
            n = self.sensor_frames_stored + self.sensor_i - self.sensor_last_i

        # calculate next velocity:
        # v2 = v1 + a1*t1+a2*t2+...
        v = self.v_old + np.sum(new_accels, axis = 1)*np.true_divide(t,n) # sum along each dimension

        # calculate next 
        # d = v_avg*dt
        d = (self.v_old + v)/2*t

        # transform by angles - heading and pitch
        pitch = self.gyro[self.gyro_pitch_axis,self.sensor_i]

        heading_old = self.heading;
        # magnetometer heading
        self.heading_mag = self.heading_mag*(1-self.mag_filter_rate) + self.mag_filter_rate*(np.arctan2((self.mag[0,self.sensor_i]-3300)*1,(self.mag[1,self.sensor_i]+410)*2) - self.zero_angle)

        #if self.mag[0,self.sensor_i] < self.magx[0]:
        #    self.magx[0] = self.mag[0,self.sensor_i]
        #elif self.mag[0,self.sensor_i] > self.magx[1]:
        #    self.magx[1] = self.mag[0,self.sensor_i]
        #if self.mag[1,self.sensor_i] < self.magy[0]:
        #    self.magy[0] = self.mag[1,self.sensor_i]
        #elif self.mag[1,self.sensor_i] > self.magy[1]:
        #    self.magy[1] = self.mag[1,self.sensor_i]
            
        #offsetx = (self.magx[1] + self.magx[0])/2
        #offsety = (self.magy[1] + self.magy[0])/2

        #magnitudex = self.magx[0] + self.magx[1]
        #magnitudey = self.magy[0] + self.magy[1]

        #print("min and max x and y: " + str([self.magx, self.magy]))
        #print("Offset x and y: " + str([offsetx, offsety]))
        
        x_n = self.x_n_1 + np.sum(new_gyros[2,:]-self.gyro_zero)*self.gyro_gain*t/n
        w_n = self.gyro_filter_rate*self.x_n_1+(1-self.gyro_filter_rate)*self.w_n_1
        self.heading_gyro = self.gyro_filter_rate*x_n+(1-self.gyro_filter_rate)*w_n
        self.w_n_1 = w_n
        self.x_n_1 = x_n
        

        heading_old = self.heading;
        self.heading = self.heading_gyro*self.gyro_mag_ratio+self.heading_mag*(1-self.gyro_mag_ratio)

        heading_curr = self.heading+heading_old/2
        #print(heading_curr)
        #print(pitch)
        dx = -d[0]*np.cos(heading_curr)*np.cos(pitch)
        dy = -d[0]*np.sin(heading_curr)*np.cos(pitch)
        
        #fix units
        dx = dx * 32.174 * 12
        dy = dy * 32.174 * 12



        # increment index
        #xy_i = (xy_i + 1) % xy_frames_stored

        return dx,dy,self.heading, self.confirm_distance()


    def zero_gyro(self):
        nine_dof_lock.acquire()
        gyro_sum = 0
        for n in range(200):
            gyro_sum += lsm.readGyro()[2]
            time.sleep(.01)
        nine_dof_lock.release()
        mag = lsm.readMag()
        zero_mag = np.arctan2((mag[0]-3300)*1,(mag[1]+410)*2) 

        self.gyro_zero = gyro_sum/n + self.zero_angle - zero_mag


    def confirm_distance(self):
        return 1 # for now

        # new way:
        # cumulatively sum distances since last encoder reading
        # when encoder is read - compare to accel distance
        # if too far off - skipping
        # otherwise - correct? maybe (imperfect because doesn't account for all directional stuff
        # TODO: how to deal with turns???

        # DUMB WAY - a = delta v - only works if >= 1 encoder sample per read_displacement() call
        # skid_err_range depends on this too

        # enc_a = r(xy_i) - r(xy_i-1) 
        # accel_a = np.sum(accel(n,:))/(accel.shape[1]) # TODO fill in n for correct dim - i.e. rover's "fwd"
        #if np.abs(accel_a-enc_a)/(accel_a) > skid_err_range # if error is too large
        # TODO would it be better to use flat error range? i.e. 
        #    return 0
        #else
        #    return 1
        
        # new way - assume that the only errors will be skidding - i.e. wheels report faster speed than accel indicates
        # still using shit encoders though
        # first_nonzero = find(r)[1] # 
        # 
        # v = sum(r[first_nonzero:second_nonzero])/(second_nonzero-first_nonzero)

        # if (v == 1): # when encoder triggers
        #   v_progress = v_old # store last v count 

        # enc_a = v - v_old
        # 
        # accel_a = np.sum(accel(n,:))/(accel.shape[1]) # TODO fill in n for correct dim - i.e. rover's "fwd"

        # v_progress = v

        # if ((enc_a - accel_a) / accel_a > skid_err_range)
        #   return 0
        # else 
        #   return 1 
        # 
