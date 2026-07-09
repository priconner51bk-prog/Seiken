
from PIL import Image,ImageDraw,ImageFont
import random
import sys
import os
import math
import datetime

from concurrent.futures import ProcessPoolExecutor,as_completed,wait

class Roulette():
    size=200
    fps=30
    fonts=[("./font/Nikumaru.otf",20,"にくまるフォント")]
    
    @staticmethod
    def drawing(names:list,colors:list,frame,i):
        """
        frames:list フレームごとの角度
        """
        size=(Roulette.size,Roulette.size+50+len(names)*20)
        rrange=[size[0]/6,size[0]/6,size[0]/6*5,size[0]/6*5]
        rad=360/len(names)
        font=Roulette.fonts[0]
        theta=frame
        im=Image.new('RGB',size,(255,255,255))
        draw=ImageDraw.Draw(im)
        for count,name in enumerate(names):
            draw.pieslice(rrange,start=rad*count+theta,end=rad*(count+1)+theta,fill=colors[count],outline=(0,0,0))
            draw.rectangle((size[0]/6,size[0]+count*20,size[0]*2/6,size[0]+(count+1)*20),fill=colors[count])
            draw.rectangle((size[0]*2/6,size[0]+count*20,size[0],size[0]+(count+1)*20),fill=(255,255,255),outline=(0,0,0))
            draw.text((size[0]*2/6,size[0]+count*20),name,(0,0,0),font=ImageFont.truetype(font[0],font[1]))
        draw.pieslice((size[0]/3,size[0]/3,size[0]/3*2,size[0]/3*2),start=0,end=360,fill=(255,255,255),outline=(0,0,0))
        draw.polygon(((size[0]*24/50,size[0]/6*0.8),(size[0]*26/50,size[0]/6*0.8),(size[0]/2,size[0]/6*1.1)),fill=(255,0,255),outline=(0,0,0))
        return im,i

    @staticmethod
    def roulette_multi(args):
        names=args
        if len(names)<=1 or __name__ != "__main__":
            return None
        colors=[]
        for count in range(len(names)):
            colors.append((random.randint(150,255),random.randint(150,255),random.randint(150,255)))
        font=Roulette.fonts[0]

        size=(Roulette.size,Roulette.size+50+len(names)*20)
        rrange=[size[0]/6,size[0]/6,size[0]/6*5,size[0]/6*5]
        rad=360/len(names)
        omega=5
        theta=0
        frame=0
        frames=[]
        switching=random.randint(15,23)
        ac_frame=0
        while True:
            frames.append(theta)
            theta+=omega
            if omega < 135 and ac_frame == 0:
                omega+=(1+random.uniform(0,7.0))*20/Roulette.fps
                if omega >= 135:
                    ac_frame = frame
            elif frame<= ac_frame + switching:
                #omega+=0
                pass
            elif omega>0:
                if omega > 2:
                    omega-=(int(omega/35)+random.uniform(0,0.3))*20/Roulette.fps
                omega-=(0.05+random.uniform(0,0.1))*20/Roulette.fps
            else:
                break
            frame+=1

        result=[]
        with ProcessPoolExecutor() as process:
            futures=[process.submit(Roulette.drawing,names,colors,_frame,i) for i,_frame in enumerate(frames)]
            for future in as_completed(futures):
                # 終わった処理のindexを追加
                result.append(future.result())  
        images=[v[0] for v in sorted(result,key=lambda x:x[1])]

        ###############################################################
        # 結果表示
        ###############################################################
        im=Image.new('RGB',size,(255,255,255))
        draw=ImageDraw.Draw(im)
        res=math.floor((270-theta+360)/rad)%len(names)
        for count,name in enumerate(names):
            draw.pieslice(rrange,start=rad*count+theta,end=rad*(count+1)+theta,fill=colors[count],outline=(0,0,0))
            draw.rectangle((size[0]/6,size[0]+count*20,size[0]*2/6,size[0]+(count+1)*20),fill=colors[count])
            draw.rectangle((size[0]*2/6,size[0]+count*20,size[0],size[0]+(count+1)*20),outline=(0,0,0))
            draw.text((size[0]*2/6,size[0]+count*20),name,(0,0,0),font=ImageFont.truetype(font[0],font[1]))
        draw.pieslice((size[0]/3,size[0]/3,size[0]/3*2,size[0]/3*2),start=0,end=360,fill=(255,255,255),outline=(0,0,0))
        draw.polygon(((size[0]*24/50,size[0]/6*0.8),(size[0]*26/50,size[0]/6*0.8),(size[0]/2,size[0]/6*1.1)),fill=(255,0,255),outline=(0,0,0))
        draw.rectangle((size[0]*2/6,size[0]+res*20,size[0],size[0]+(res+1)*20),outline=(255,0,0),fill=(255,200,200))
        draw.text((size[0]*2/6,size[0]+res*20),names[res],(0,0,0),font=ImageFont.truetype(font[0],font[1]))
        draw.text((size[0]/2,size[0]/2),names[res],(0,0,0),font=ImageFont.truetype(font[0],math.ceil(size[0]/8)),anchor="mm")
        images.append(im)
        return images,res
    
if __name__ == "__main__":
    filename=""
    args=sys.argv
    if len(args)>=3:
        images,res=Roulette.roulette_multi(args[1:])
        os.makedirs("roulette_result",exist_ok=True)
        filename=f"roulette_result/roulette_multi_{ datetime.datetime.now().strftime('%Y-%m-%d--%H-%M-%S-%f')}.gif"
        images[0].save(fp=filename,format="gif",save_all=True,append_images=images[1:],optimize=False,duration=1000/Roulette.fps)
    print(filename + " " + str(res))