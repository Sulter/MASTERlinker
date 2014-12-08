from random import randrange



#Rolls a random number.

class roll():

    

	def roll(self, main_ref, msg_info):
        
		if not msg_info["message"].startswith("!roll"):
            
			return None

		

		input = msg_info["message"].replace("!roll","")
	

		if not self.is_number(input):
			return None
			
		
		response = str(randrange((int)(input)))		
		
		
		main_ref.send_msg(msg_info["channel"], response)


	def is_number(self, s):
	    try:
        	int(s)
	        return True
	    except ValueError:
        	return False
	