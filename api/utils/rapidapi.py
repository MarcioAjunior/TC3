import os
import requests
from utils.clean_comment import clean_comment_text
from fastapi import HTTPException
import joblib

def fetch_profile_posts(username:str = '', is_traning = False):
    
    params = {'username_or_id_or_url':username}
    
    headers = {
            'x-rapidapi-host' : 'instagram-scraper-api2.p.rapidapi.com',
            'x-rapidapi-key': os.getenv("RAPID_API_KEY")
            }
    
    r = requests.get('https://instagram-scraper-api2.p.rapidapi.com/v1.2/posts', params=params, headers=headers)
    
    if r.status_code == 404:
        raise HTTPException(status_code=404, detail="Usuário não encontrado !")
    
    r.raise_for_status()    
    data = r.json()
    
    id = data.get('data', {}).get('user',{}).get('id','')

    profile = {
        'id' : id, 
        'username' : username, 
        'user_fullname' : data.get('data', {}).get('user',{}).get('full_name',''),
        'user_picture' : data.get('data', {}).get('user',{}).get('profile_pic_url',''),
        'is_training' : is_traning
    } 
    
    raw_posts = data.get('data', {}).get('items',[])

    posts = []
    
    for raw_post in raw_posts:        
        
        if raw_post.get('caption') is not None:
            if raw_post.get('caption',{}).get('content_type') == 'comment':
                post_text = clean_comment_text(raw_post.get('caption',{}).get('text'))
            else:
                post_text = ''   

        post = {
            'id': raw_post.get('id',''),
            'at_insta' : raw_post.get('taken_at',''),
            'post_url' : f'https://www.instagram.com/p/{raw_post.get("code","")}',
            'thumb_url' : raw_post.get('thumbnail_url',''),
            'post_text':  post_text,
            'user_id' :  id,
        }

        posts.append(post)
        
    return profile, posts

def fetch_comments(posts:list = [], is_classification = True):
    
    comments = []
    
    if len(posts) > 0:
        
        threshold = float(os.getenv("THRESHOLD"))
        model = joblib.load(os.path.join(os.path.dirname(__file__), 'best_model.pkl'))
            
        for post in posts:
            
            id = post['id']

            params = {
                'code_or_id_or_url':id,
                'sort_by':'popular'
                }
        
            headers = {
                    'x-rapidapi-host' : 'instagram-scraper-api2.p.rapidapi.com',
                    'x-rapidapi-key': os.getenv("RAPID_API_KEY")
                    }
        
            r = requests.get('https://instagram-scraper-api2.p.rapidapi.com/v1/comments', params=params, headers=headers)
            
            if r.status_code == 404:
                raise HTTPException(status_code=500, detail="Comentários não localizado")
            if r.status_code == 403:
                continue #forbiden
            
            r.raise_for_status()    
            data = r.json()
            
            if data.get('data',{}).get('items', []) is None:
                continue
            
            raw_comments = data.get('data',{}).get('items', [])
            
            number_of_comments = int(os.getenv("NUMBER_OF_COMMENTS"))
            
            if len(raw_comments) > number_of_comments:
                raw_comments = raw_comments[:number_of_comments]

            for raw_comment in raw_comments:
                
                comment_txt = ''
                
                if raw_comment.get('type','') != 2: #verify
                    
                    comment_txt = clean_comment_text(raw_comment.get('text',''))
                    #comment_txt = 'TEXTO'
                                        
                    if comment_txt != '':
                        
                        classification = ''
                        
                        if is_classification:
                            try :                         
                                vectorizer = model.named_steps['tfidf']
                                classifier  = model.named_steps['logisticregression']
                                                                
                                comment_vec = vectorizer.transform([comment_txt])
                                probabilities = classifier.predict_proba(comment_vec)
                                
                                max_prob = float(max(probabilities[0]))
                                pred_class = classifier.classes_[probabilities[0].argmax()]
                                                            
                                if max_prob < threshold:
                                    classification = 'NEUTRO'
                                else:
                                    if pred_class == 1:
                                        classification = 'BOM'
                                    elif pred_class == 0:
                                        classification = 'RUIM'
                                    else :
                                        classification = 'NEUTRO'
                                    
                            except Exception as e:
                                print(e)
                            
                            
                        comment = {
                            'id' : raw_comment.get('id',''),
                            'at_insta' : raw_comment.get('created_at',''),
                            'comment_text' : comment_txt,
                            'classification' : classification,
                            'verified_class' : False,
                            'post_id' : id
                        }

                        comments.append(comment)
                
    return comments